"""Run the host: `python -m voice_display_host`.

The example lanes are here rather than in the library because they are an
example. Point `MCP_URL` at your own server and write your own.
"""

from __future__ import annotations

import os

import uvicorn

from voice_display_host.app import build_app
from voice_display_host.config import Settings
from voice_display_host.router import FastLane, Router, bedrock_router

EXAMPLE_LANES = (
    FastLane(
        tool="get_today",
        matches=(r"\btoday\b", r"what'?s? (on|up)\b", r"\bdate\b", r"\bopen(ing)?\b"),
        # A date in the past or future is a different question, and
        # answering it with today's is a wrong answer, not a slow one.
        declines=(r"\byesterday\b", r"\btomorrow\b", r"\blast (week|month|year)\b"),
    ),
    FastLane(
        tool="start_timer",
        matches=(r"\btimer\b", r"\bremind me in\b", r"\bcount ?down\b"),
    ),
)


def main() -> None:
    settings = Settings.from_env()
    route_with_model = (
        bedrock_router(settings.router_model, settings.aws_region)
        if settings.uses_model_router
        else None
    )
    router = Router(
        lanes=EXAMPLE_LANES,
        model_route=route_with_model,
        fallback_tool=os.environ.get("FALLBACK_TOOL", "get_today"),
    )
    app = build_app(settings, router, client_dir=os.environ.get("CLIENT_DIR") or None)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), log_level="info")


if __name__ == "__main__":
    main()
