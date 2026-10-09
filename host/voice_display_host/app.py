"""The HTTP face of the host: three endpoints and a static client.

    POST /turn    one utterance in, words + card out
    POST /speak   text in, mp3 out, when a voice is configured
    GET  /health  is it up
    GET  /card    the card's HTML, proxied from the MCP server

`/card` exists because the card runs in a sandboxed iframe with an opaque
origin and cannot fetch anything itself. The display asks the host, the
host asks the MCP server over the session it already has.
"""

from __future__ import annotations

import json
from typing import Any

import anyio.to_thread
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from voice_display_host.agent import run_turn
from voice_display_host.config import Settings
from voice_display_host.guard import RateLimiter, cap, client_ip
from voice_display_host.router import Router

TOO_MANY = "Easy — too many requests. Give it a moment."
TOO_BIG = "That request is too large."


def build_app(
    settings: Settings | None = None,
    router: Router | None = None,
    client_dir: str | None = None,
) -> Starlette:
    """The ASGI app. `router` is yours to supply; the default routes nothing."""
    config = settings or Settings.from_env()
    routing = router or Router()
    per_visitor = RateLimiter(per_minute=config.turns_per_minute_per_visitor)
    per_address = RateLimiter(per_minute=config.turns_per_minute_per_ip)

    def refuse(message: str, status: int, key: str = "") -> JSONResponse:
        # A refusal is a sentence, not an exception: the display reads the
        # server's own words aloud when they read like something a person
        # would say, so "Easy — too many requests" beats a stack trace.
        headers = {}
        if status == 429 and key:
            headers["retry-after"] = str(per_visitor.retry_after(key))
        return JSONResponse({"error": message}, status_code=status, headers=headers)

    async def turn(request: Request) -> Response:
        raw = await request.body()
        if len(raw) > config.max_body_bytes:
            return refuse(TOO_BIG, 413)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return refuse("That request was not JSON.", 400)
        if not isinstance(payload, dict):
            return refuse("That request was not an object.", 400)

        utterance = cap(
            payload.get("utterance") or payload.get("text") or "",
            config.max_utterance_chars,
        )
        if not utterance.strip():
            return refuse("Nothing was said.", 400)

        visitor = cap(str(payload.get("visitorId") or "anonymous"), 128)
        peer = request.client.host if request.client else None
        address = client_ip(request.headers.get("x-forwarded-for"), peer)
        if not per_address.allow(address):
            return refuse(TOO_MANY, 429, address)
        if not per_visitor.allow(visitor):
            return refuse(TOO_MANY, 429, visitor)

        try:
            answered = await run_turn(utterance, mcp_url=config.mcp_url, router=routing)
        except Exception as exc:
            return JSONResponse(
                {
                    "spoken": "I couldn't reach the server behind this. Try that again?",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                status_code=502,
            )
        return JSONResponse({**answered.as_dict(), "visitorId": visitor})

    async def speak(request: Request) -> Response:
        if not config.uses_polly:
            # Not an error: the client falls back to its own speechSynthesis.
            return Response(status_code=204)
        payload = json.loads(await request.body() or b"{}")
        text = cap(str(payload.get("text") or ""), config.max_utterance_chars)
        from voice_display_host.tts import synthesize

        audio = await anyio.to_thread.run_sync(
            synthesize, text, config.tts_voice, config.tts_engine, config.aws_region
        )
        if not audio:
            return Response(status_code=204)
        return Response(audio, media_type="audio/mpeg")

    async def card(request: Request) -> Response:
        """One card's HTML, read from the MCP server by uri."""
        uri = request.query_params.get("uri", "")
        if not uri.startswith("ui://"):
            return refuse("That is not a card uri.", 400)
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        try:
            async with streamable_http_client(config.mcp_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    got = await session.read_resource(uri)  # type: ignore[arg-type]
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)

        for item in getattr(got, "contents", None) or []:
            text = getattr(item, "text", None)
            if isinstance(text, str) and text.strip():
                return Response(
                    text,
                    media_type="text/html",
                    headers={"cache-control": "no-cache"},
                )
        return JSONResponse({"error": "that card has no html"}, status_code=404)

    async def health(_: Request) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "mcp_url": config.mcp_url,
                "router": "model" if config.uses_model_router else "rules",
                "speech": "polly" if config.uses_polly else "browser",
            }
        )

    routes: list[Any] = [
        Route("/turn", turn, methods=["POST"]),
        Route("/speak", speak, methods=["POST"]),
        Route("/card", card, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
    ]
    app = Starlette(routes=routes)
    if client_dir:
        # index.html must not be cached: it is the one file whose name never
        # changes, and it is the file that names the hashed bundles. A stale
        # copy loads the previous build's assets and shows a client nobody
        # shipped, with nothing on screen to say it is stale.
        app.mount("/", StaticFiles(directory=client_dir, html=True), name="client")
    return app
