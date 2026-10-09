"""Deciding which tool answers an utterance.

Routing is a bargain. A model reads anything and costs a round trip and a
few cents; a rule reads one shape of sentence and costs nothing. The useful
arrangement is both, in that order: rules first for the handful of things
people say constantly and say the same way, the model for the long tail.

Two things learned the hard way, building a display on top of this,
that shaped the design:

- **A rule that is not certain should decline.** Answering the wrong
  question quickly is worse than answering the right one slowly.
- **A model offered two defensible tools will pick the broader one.** If
  one tool's output contains another's, routing will drift to the container
  and every assertion downstream still passes, because the answer is not
  wrong — just much more than was asked. Make the narrow case a rule.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

#: A chosen tool call: the name and the arguments to call it with.
Choice = tuple[str, dict[str, Any]]


@dataclass(frozen=True)
class FastLane:
    """One rule: an utterance shape, the tool it means, and fixed arguments.

    `declines` is the half that matters. A lane for "what is on today"
    should refuse "what was on last Tuesday" rather than answer it with
    today's list, so a lane carries the patterns that disqualify it as well
    as the ones that match.
    """

    tool: str
    matches: Sequence[str]
    declines: Sequence[str] = ()
    arguments: dict[str, Any] = field(default_factory=dict)

    def claims(self, utterance: str) -> bool:
        said = (utterance or "").strip()
        if not said:
            return False
        if any(re.search(p, said, re.I) for p in self.declines):
            return False
        return any(re.search(p, said, re.I) for p in self.matches)


class Router:
    """Rules first, then an optional model, then a named fallback tool."""

    def __init__(
        self,
        lanes: Sequence[FastLane] = (),
        model_route: Callable[[str, list[Any]], Choice | None] | None = None,
        fallback_tool: str = "",
        fallback_argument: str = "question",
    ) -> None:
        self._lanes = list(lanes)
        self._model_route = model_route
        self._fallback_tool = fallback_tool
        self._fallback_argument = fallback_argument

    def route(self, utterance: str, tools: list[Any]) -> Choice | None:
        """The tool to call, or None when nothing can answer.

        `tools` is the server's own tool list, so a lane for a tool this
        server does not publish is skipped rather than called into the void.
        """
        names = {getattr(tool, "name", "") for tool in tools}

        for lane in self._lanes:
            if lane.tool in names and lane.claims(utterance):
                return lane.tool, dict(lane.arguments)

        if self._model_route is not None:
            chosen = self._model_route(utterance, tools)
            if chosen and chosen[0] in names:
                return chosen

        if self._fallback_tool and self._fallback_tool in names:
            return self._fallback_tool, {self._fallback_argument: utterance}
        return None


def bedrock_router(
    model_id: str, region: str, system_prompt: str = ""
) -> Callable[[str, list[Any]], Choice | None]:
    """A tool-use router over Bedrock Converse. Optional, and off by default.

    boto3 is synchronous, so the caller is expected to run this on a worker
    thread — see `agent.py`. Calling it straight from an async handler holds
    the event loop for the whole round trip and quietly serializes every
    other visitor's turn.
    """

    def route(utterance: str, tools: list[Any]) -> Choice | None:
        import boto3

        client = boto3.Session(region_name=region).client("bedrock-runtime")
        spec = {
            "tools": [
                {
                    "toolSpec": {
                        "name": tool.name,
                        "description": (getattr(tool, "description", "") or tool.name)[:900],
                        "inputSchema": {"json": getattr(tool, "input_schema", None) or {}},
                    }
                }
                for tool in tools
            ]
        }
        response = client.converse(
            modelId=model_id,
            system=[{"text": system_prompt}] if system_prompt else [],
            messages=[{"role": "user", "content": [{"text": utterance}]}],
            toolConfig=spec,
            inferenceConfig={"maxTokens": 512, "temperature": 0.0},
        )
        for block in response.get("output", {}).get("message", {}).get("content", []):
            use = block.get("toolUse")
            if use:
                return str(use.get("name") or ""), dict(use.get("input") or {})
        return None

    return route
