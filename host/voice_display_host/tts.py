"""Spoken answers, when a voice service is configured.

Off by default. With no voice set, the host returns no audio and the client
speaks the answer with the browser's own `speechSynthesis` — which is why
this repo runs end to end with no cloud account at all.

Two things worth knowing if you turn Polly on:

- **Build the client once.** A boto3 client per request spends more time
  resolving credentials than synthesizing; caching it took a measured 1.7s
  turn to 0.6s.
- **Neural, not generative, for a display.** Generative voices sound better
  and arrive later, and on a screen where the card is already up the wait
  is the thing people notice.
"""

from __future__ import annotations

import functools
from typing import Any


@functools.lru_cache(maxsize=1)
def _client(region: str) -> Any:
    import boto3

    return boto3.Session(region_name=region).client("polly")


def synthesize(text: str, voice: str, engine: str, region: str) -> bytes:
    """MP3 for one answer, or empty bytes when speech is not configured."""
    if not text.strip() or not voice:
        return b""
    response = _client(region).synthesize_speech(
        Text=text, VoiceId=voice, Engine=engine, OutputFormat="mp3"
    )
    return bytes(response["AudioStream"].read())
