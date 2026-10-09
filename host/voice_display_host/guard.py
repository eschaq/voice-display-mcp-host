"""Caps and rate limits, for a host whose URL is meant to be handed out.

Two buckets per turn, and the pairing is the point. A visitor id is minted
by the browser, so it is the right unit for "one person is going too fast"
and the wrong unit for abuse: a script can mint a new one per request. An
address is the opposite — right for abuse, wrong for people, because a
conference wifi is one address and a hundred visitors.

So: a tight limit per visitor, and a looser ceiling per address behind it.
A loop that rotates visitor ids still meets the address ceiling; a room
full of real people never reaches it.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


def client_ip(forwarded: str | None, peer: str | None, hops: int = 0) -> str:
    """Who the client is, read from the right.

    A client can send its own `X-Forwarded-For` and a proxy appends to it
    rather than replacing it, so the left-hand entries are whatever the
    caller wanted them to be. Reading from the left lets an attacker pick
    their own bucket and get a fresh one every request — a limiter that
    does nothing while looking like it works. `hops` is how many proxies of
    your own sit in front; the entry that many places from the right is the
    first one you did not write.
    """
    entries = [part.strip() for part in (forwarded or "").split(",") if part.strip()]
    if len(entries) > hops:
        return entries[-(hops + 1)]
    return (peer or "unknown").strip() or "unknown"


@dataclass
class RateLimiter:
    """A sliding window per key. In memory, so it is per process."""

    per_minute: int
    _seen: dict[str, deque[float]] = field(default_factory=dict)

    def allow(self, key: str, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        window = self._seen.setdefault(key, deque())
        while window and moment - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.per_minute:
            return False
        window.append(moment)
        return True

    def retry_after(self, key: str, now: float | None = None) -> int:
        moment = now if now is not None else time.monotonic()
        window = self._seen.get(key)
        if not window:
            return 0
        return max(1, int(60.0 - (moment - window[0])) + 1)


def cap(text: str | None, limit: int) -> str:
    """Trim to a length rather than refuse. A long utterance is still a
    question; it is only the unbounded one that is a problem."""
    return (text or "")[:limit]
