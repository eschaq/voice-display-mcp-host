"""Routing: rules first, the model for the rest, and a lane that declines."""

from __future__ import annotations

from dataclasses import dataclass

from voice_display_host.router import FastLane, Router


@dataclass
class FakeTool:
    name: str
    description: str = ""
    input_schema: dict | None = None


TOOLS = [FakeTool("get_today"), FakeTool("start_timer"), FakeTool("ask_anything")]

LANES = (
    FastLane(
        tool="get_today",
        matches=(r"\btoday\b", r"what'?s? on\b"),
        declines=(r"\byesterday\b", r"\btomorrow\b"),
    ),
    FastLane(tool="start_timer", matches=(r"\btimer\b",), arguments={"minutes": 5}),
)


def test_a_lane_claims_the_utterance_it_is_for() -> None:
    router = Router(lanes=LANES)
    assert router.route("What's on today?", TOOLS) == ("get_today", {})


def test_a_lane_carries_its_fixed_arguments() -> None:
    router = Router(lanes=LANES)
    assert router.route("set a timer", TOOLS) == ("start_timer", {"minutes": 5})


def test_a_lane_declines_rather_than_answering_the_wrong_question() -> None:
    """Answering "what was on yesterday" with today's list is a wrong
    answer, not a slow one. The lane steps aside and the model decides."""
    router = Router(lanes=LANES, fallback_tool="ask_anything")
    assert router.route("What was on yesterday?", TOOLS) == (
        "ask_anything",
        {"question": "What was on yesterday?"},
    )


def test_the_model_only_runs_when_no_lane_claims_it() -> None:
    calls: list[str] = []

    def model(utterance: str, _tools: list) -> tuple[str, dict]:
        calls.append(utterance)
        return "ask_anything", {"question": utterance}

    router = Router(lanes=LANES, model_route=model)
    assert router.route("today?", TOOLS) == ("get_today", {})
    assert calls == [], "a lane matched and the model was paid for anyway"

    router.route("how tall is the tower", TOOLS)
    assert calls == ["how tall is the tower"]


def test_a_tool_the_server_does_not_publish_is_never_called() -> None:
    """Tool lists differ per server; a lane for a missing tool steps aside."""
    router = Router(lanes=LANES, fallback_tool="ask_anything")
    only_timer = [FakeTool("start_timer"), FakeTool("ask_anything")]
    assert router.route("what's on today?", only_timer) == (
        "ask_anything",
        {"question": "what's on today?"},
    )


def test_a_model_choice_for_an_unknown_tool_is_refused() -> None:
    router = Router(lanes=(), model_route=lambda u, t: ("not_a_tool", {}))
    assert router.route("anything", TOOLS) is None


def test_nothing_to_call_is_none_rather_than_a_guess() -> None:
    assert Router().route("anything at all", TOOLS) is None
