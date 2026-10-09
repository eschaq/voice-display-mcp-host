"""The tool's words reach the person unchanged.

A host that lets a model rewrite a tool result will round "28.6%" to
"about a third" and put a number on screen that the card beside it
disagrees with — and every content assertion still passes, because the
paraphrase is not wrong, only different. So the text is passed through.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from voice_display_host.agent import spoken_from, ui_resource_for


@dataclass
class Block:
    text: str
    type: str = "text"


@dataclass
class Result:
    content: list[Block] = field(default_factory=list)


def test_the_tools_sentence_is_what_gets_spoken() -> None:
    said = spoken_from(Result([Block("Four jobs today, first one at 8:30.")]))
    assert said == "Four jobs today, first one at 8:30."


def test_a_serialised_payload_is_never_read_aloud() -> None:
    """A structured result is often also stringified into a text block by
    the SDK. A host that speaks every block reads JSON out loud."""
    said = spoken_from(Result([Block('{"count": 4, "first": "8:30"}'), Block("Four jobs today.")]))
    assert said == "Four jobs today."


def test_a_json_looking_sentence_is_still_a_sentence() -> None:
    said = spoken_from(Result([Block("{not actually json")]))
    assert said == "{not actually json"


def test_several_blocks_join_in_order() -> None:
    said = spoken_from(Result([Block("Done, flagged."), Block("Margin landed at 26%.")]))
    assert said == "Done, flagged. Margin landed at 26%."


# --- which card to draw ------------------------------------------------


@dataclass
class ToolWithView:
    name: str = "get_today"
    meta: dict | None = field(default_factory=lambda: {"ui": {"resourceUri": "ui://example/today"}})


def test_a_tools_bound_view_is_used() -> None:
    assert ui_resource_for(ToolWithView(), None) == "ui://example/today"


def test_a_result_may_choose_its_own_view() -> None:
    """One tool that answers anything needs a card per answer, not per tool."""
    chosen = ui_resource_for(ToolWithView(), {"ui_resource_uri": "ui://example/timer"})
    assert chosen == "ui://example/timer"


def test_a_tool_with_no_view_draws_nothing() -> None:
    @dataclass
    class Bare:
        name: str = "plain"
        meta: dict | None = None

    assert ui_resource_for(Bare(), None) is None
