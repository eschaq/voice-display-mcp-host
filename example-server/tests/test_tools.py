"""The example server publishes what it says it publishes.

This test exists because of a specific silent failure: `@apps.tool` applied
to a function defined *after* `MCPServer(...)` is constructed registers
nothing. The extension's tools are snapshotted at construction, so the card
is served, the tool vanishes from the list, and there is no error anywhere.
Counting the tools is the only thing that catches it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import TIMER_UI_URI, TODAY_UI_URI, mcp

EXPECTED_TOOLS = {"get_today", "start_timer"}


def test_every_tool_is_published() -> None:
    names = {tool.name for tool in anyio.run(mcp.list_tools)}
    assert names == EXPECTED_TOOLS, f"published {sorted(names)}"


def test_each_tool_is_bound_to_its_card() -> None:
    bound = {}
    for tool in anyio.run(mcp.list_tools):
        meta = getattr(tool, "meta", None) or {}
        ui = (meta.get("ui") or {}) if isinstance(meta, dict) else {}
        if ui.get("resourceUri"):
            bound[tool.name] = ui["resourceUri"]
    assert bound == {"get_today": TODAY_UI_URI, "start_timer": TIMER_UI_URI}


def test_every_card_uri_is_served() -> None:
    served = {str(resource.uri) for resource in anyio.run(mcp.list_resources)}
    assert {TODAY_UI_URI, TIMER_UI_URI} <= served


def test_a_card_carries_its_bridge_and_fit() -> None:
    """The slots are filled at load, so an unfilled one is a dead card."""
    from server import load_card

    for name in ("today", "timer"):
        html = load_card(name)
        assert "/* BRIDGE */" not in html and "/* FIT */" not in html, name
        assert "ui/initialize" in html, f"{name} has no handshake"
        assert "fitToBand" in html, f"{name} cannot scale to its box"
