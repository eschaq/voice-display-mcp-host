"""A tiny MCP server, so the repo runs end to end with nothing to sign up for.

Two tools and one MCP App card. The point is not what it does — it tells
you the date and counts down — but that it is a complete, correct example
of the shape: Streamable HTTP, a card served as an `ui://` resource with a
CSP, and a tool bound to that card so the host knows what to draw.

    python example-server/server.py        # http://127.0.0.1:8081/mcp
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent

CARDS = Path(__file__).resolve().parent / "cards"

TODAY_UI_URI = "ui://example/today"
TIMER_UI_URI = "ui://example/timer"


def public_origin() -> str:
    """Where a card may load its own fonts and images from.

    A card runs in a sandboxed iframe with an opaque origin, so a relative
    url resolves to the sandbox and a `'self'` CSP means the sandbox too.
    The absolute origin is the only thing that works, which is why it is
    the one domain the card's CSP widens to.
    """
    return os.environ.get("PUBLIC_ORIGIN", "http://127.0.0.1:8080").rstrip("/")


CARD_CSP = ResourceCsp(resource_domains=[public_origin()])


def load_card(name: str) -> str:
    """A card's HTML with the shared bridge and fit script inlined.

    A card can link nothing at runtime, so "shared" has to mean inlined
    here rather than imported there. Both slots are required: a card
    missing one would ship a handshake that never runs and fail silently.
    """
    html = (CARDS / f"{name}.html").read_text(encoding="utf-8")
    for slot, source in (("/* BRIDGE */", "_bridge.js"), ("/* FIT */", "_fit.js")):
        if slot not in html:
            raise ValueError(f"{name}.html has no {slot} slot")
        html = html.replace(slot, (CARDS / source).read_text(encoding="utf-8"))
    return html


apps = Apps()
for uri, name in ((TODAY_UI_URI, "today"), (TIMER_UI_URI, "timer")):
    apps.add_html_resource(
        uri,
        load_card(name),
        csp=CARD_CSP,
        name=f"example-{name}-card",
        title=name.title(),
        description=f"The {name} card for the example server.",
    )


# Every @apps.tool must be defined BEFORE MCPServer is constructed. The
# server snapshots an extension's tools at construction, so a decorator
# that runs later serves the resource and never registers the tool — it
# simply vanishes from the list, with no error anywhere. See the README.
@apps.tool(resource_uri=TODAY_UI_URI)
def get_today() -> CallToolResult:
    """What today is, and how far through the year it is.

    Use for "what's today", "what's the date", "what's on".
    """
    today = date.today()
    start = date(today.year, 1, 1)
    day_of_year = (today - start).days + 1
    in_year = (
        366
        if (today.year % 4 == 0 and today.year % 100 != 0) or today.year % 400 == 0
        else 365
    )
    spoken = (
        f"It's {today.strftime('%A, %B %-d')}. "
        f"Day {day_of_year} of {in_year} — about {round(100 * day_of_year / in_year)}% "
        "of the way through the year."
    )
    return CallToolResult(
        content=[TextContent(type="text", text=spoken)],
        structured_content={
            "weekday": today.strftime("%A"),
            "date_text": today.strftime("%B %-d, %Y"),
            "iso": today.isoformat(),
            "day_of_year": day_of_year,
            "days_in_year": in_year,
            "percent_through": round(100 * day_of_year / in_year),
        },
    )


@apps.tool(resource_uri=TIMER_UI_URI)
def start_timer(minutes: int = 5, label: str = "timer") -> CallToolResult:
    """Start a countdown and put it on screen.

    Use for "set a timer for ten minutes", "remind me in an hour".

    Args:
        minutes: How long, in minutes. Clamped to a day.
        label: What the timer is for, in a word or two.
    """
    span = max(1, min(int(minutes or 1), 24 * 60))
    ends = datetime.now() + timedelta(minutes=span)
    unit = "minute" if span == 1 else "minutes"
    return CallToolResult(
        content=[
            TextContent(
                type="text", text=f"{span} {unit} for the {label}. Starting now."
            )
        ],
        structured_content={
            "label": str(label)[:60] or "timer",
            "minutes": span,
            "ends_at": ends.isoformat(timespec="seconds"),
            "ends_text": ends.strftime("%-I:%M %p").lower(),
        },
    )


mcp: MCPServer = MCPServer("example", extensions=[apps])


def main() -> None:
    import uvicorn

    port = int(os.environ.get("EXAMPLE_PORT", "8081"))
    uvicorn.run(
        mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
