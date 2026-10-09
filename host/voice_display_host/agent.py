"""One turn: hear something, call a tool, hand back words and a card.

What this deliberately does *not* do is let a model write the answer. The
tool's own text is passed through verbatim. A model that paraphrases a
tool result will round "28.6%" to "about a third" and put a number on the
screen that the card beside it disagrees with — and every content
assertion still passes, because the paraphrase is not wrong, just
different. Routing is the model's job here; wording is not.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import anyio.to_thread

from voice_display_host.intent import card_action_for, is_sign_off
from voice_display_host.router import Router

SIGN_OFF_REPLY = "Got it."


@dataclass(frozen=True)
class Turn:
    """What the display needs to draw and say one turn."""

    spoken: str
    tool_name: str | None = None
    tools_called: list[str] = field(default_factory=list)
    ui_resource_uri: str | None = None
    structured_content: dict[str, Any] | None = None
    #: "replace" puts this turn's card up; "keep" leaves what is on screen.
    card_action: str = "replace"
    timings: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "spoken": self.spoken,
            "toolName": self.tool_name,
            "toolsCalled": list(self.tools_called),
            "uiResourceUri": self.ui_resource_uri,
            "cardAction": self.card_action,
            "structuredContent": self.structured_content,
            "timings": {key: round(value, 3) for key, value in self.timings.items()},
        }


def ui_resource_for(tool: Any, structured: dict[str, Any] | None) -> str | None:
    """The card for one tool result.

    MCP Apps binds one view per tool, which is right for a tool that
    computes one thing. A tool that answers anything needs to choose per
    call, so a result may name its own `ui://` and that wins — but only if
    the server actually publishes it, or a tool could talk the display into
    fetching something else.
    """
    chosen = (structured or {}).get("ui_resource_uri")
    if isinstance(chosen, str) and chosen:
        return chosen
    meta = getattr(tool, "meta", None) or {}
    ui = (meta.get("ui") or {}) if isinstance(meta, dict) else {}
    uri = ui.get("resourceUri")
    return str(uri) if uri else None


def spoken_from(result: Any) -> str:
    """The tool's own words, joined. Never a serialised payload.

    A structured result is often *also* stringified into the text block by
    the SDK, so a host that speaks every text block reads JSON out loud —
    which is how "desks_called" once got spoken to a room. Anything that
    parses as an object is dropped.
    """
    import json

    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not isinstance(text, str) or not text.strip():
            continue
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                continue
            except ValueError:
                pass
        parts.append(stripped)
    return " ".join(parts).strip()


async def run_turn(
    utterance: str,
    *,
    mcp_url: str,
    router: Router,
    model_in_thread: bool = True,
) -> Turn:
    """Route one utterance to a tool and return what to say and show."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    if is_sign_off(utterance):
        # No tool, no model, no round trip. Whatever is on screen stays.
        return Turn(spoken=SIGN_OFF_REPLY, card_action="keep", timings={"total": 0.0})

    started = time.perf_counter()
    timings: dict[str, float] = {}

    async with streamable_http_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            tools = list(listing.tools)
            timings["connect"] = time.perf_counter() - started

            chose = time.perf_counter()
            if model_in_thread:
                # boto3 is synchronous. Left on the event loop it holds the
                # whole process for the length of the call, so five people
                # asking at once wait in line — measured at 3-4x on a turn
                # that should overlap entirely.
                choice = await anyio.to_thread.run_sync(router.route, utterance, tools)
            else:
                choice = router.route(utterance, tools)
            timings["route"] = time.perf_counter() - chose

            if choice is None:
                timings["total"] = time.perf_counter() - started
                return Turn(
                    spoken="I don't have anything that answers that.",
                    card_action="keep",
                    timings=timings,
                )

            name, arguments = choice
            tool = next((t for t in tools if t.name == name), None)

            ran = time.perf_counter()
            result = await session.call_tool(name, arguments)
            timings["tool_call"] = time.perf_counter() - ran

            structured = (
                result.structured_content if isinstance(result.structured_content, dict) else None
            )
            timings["total"] = time.perf_counter() - started
            return Turn(
                spoken=spoken_from(result) or "Done.",
                tool_name=name,
                tools_called=[name],
                ui_resource_uri=ui_resource_for(tool, structured),
                structured_content=structured,
                card_action=card_action_for(utterance),
                timings=timings,
            )
