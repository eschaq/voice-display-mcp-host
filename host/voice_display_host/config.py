"""Everything the host reads from the environment, in one place.

Defaults are chosen so the repo runs with no cloud account at all: no model,
no speech service, and an MCP server on localhost. Setting any of these turns
a piece on rather than switching it over.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Host configuration. Read once at startup."""

    #: The MCP server this host puts a face on. Any Streamable HTTP endpoint.
    mcp_url: str = "http://127.0.0.1:8081/mcp"

    #: Bedrock model id for the routing step. Empty means rule routing only,
    #: which is the default and needs no AWS account.
    router_model: str = ""
    aws_region: str = "us-east-1"

    #: Polly voice for spoken answers. Empty means the browser speaks with
    #: its own speechSynthesis, which is the no-account path.
    tts_voice: str = ""
    tts_engine: str = "neural"

    #: Caps. A public demo link is a public demo link.
    max_utterance_chars: int = 500
    max_body_bytes: int = 64 * 1024
    turns_per_minute_per_visitor: int = 20
    turns_per_minute_per_ip: int = 60

    @classmethod
    def from_env(cls) -> Settings:
        def text(name: str, fallback: str) -> str:
            return os.environ.get(name, fallback).strip()

        def number(name: str, fallback: int) -> int:
            try:
                return int(os.environ.get(name, "").strip() or fallback)
            except ValueError:
                return fallback

        return cls(
            mcp_url=text("MCP_URL", cls.mcp_url),
            router_model=text("ROUTER_MODEL", cls.router_model),
            aws_region=text("AWS_REGION", cls.aws_region),
            tts_voice=text("TTS_VOICE", cls.tts_voice),
            tts_engine=text("TTS_ENGINE", cls.tts_engine),
            max_utterance_chars=number("MAX_UTTERANCE_CHARS", cls.max_utterance_chars),
            max_body_bytes=number("MAX_BODY_BYTES", cls.max_body_bytes),
            turns_per_minute_per_visitor=number(
                "TURNS_PER_MINUTE_PER_VISITOR", cls.turns_per_minute_per_visitor
            ),
            turns_per_minute_per_ip=number("TURNS_PER_MINUTE_PER_IP", cls.turns_per_minute_per_ip),
        )

    @property
    def uses_model_router(self) -> bool:
        return bool(self.router_model)

    @property
    def uses_polly(self) -> bool:
        return bool(self.tts_voice)
