"""What kind of thing the person just said, before any model sees it.

Two questions get answered here and both decide something concrete:

- Is this a sign-off? Then there is no tool to call and no model to pay for.
- Is this a bare confirmation? Then the card already on screen stays, because
  a "yes" is about the thing being looked at. Replacing it with a card for
  the acknowledgement takes away what was just agreed to.

Both matches are anchored at both ends. "That's it for the blue one, what
about the red?" starts like a sign-off and is a question; "Yes, and why is
it late?" starts like a confirmation and is a question. Matching a prefix
would get both wrong in the rudest possible way.
"""

from __future__ import annotations

import re

_CLOSING = (
    r"that'?s? ?(it|all|everything)",
    r"(i'?m )?(all )?done",
    r"no(thing)?( else)?",
    r"goodbye|bye|see ya",
    r"stop|cancel|never ?mind",
)
_CLOSING_TAIL = r"(,? (thanks|thank you|please|for now|mate))?"

_CONFIRMATIONS = (
    r"y(es|eah|ep|up)",
    r"ok(ay)?",
    r"sure",
    r"do it",
    r"go ahead",
    r"please do",
    r"sounds good",
    r"that'?s? ?(right|correct)",
    r"correct",
)
_CONFIRMATION_TAIL = r"(,? (please|thanks|thank you|then))?"


def _whole_match(utterance: str, patterns: tuple[str, ...], tail: str) -> bool:
    lowered = (utterance or "").strip().lower().rstrip(" .!,")
    if not lowered:
        return False
    return any(re.fullmatch(p + tail, lowered) is not None for p in patterns)


def is_sign_off(utterance: str) -> bool:
    """The whole utterance is the person finishing, not asking."""
    return _whole_match(utterance, _CLOSING, _CLOSING_TAIL)


def is_bare_confirmation(utterance: str) -> bool:
    """The whole utterance is a yes, with no question attached."""
    return _whole_match(utterance, _CONFIRMATIONS, _CONFIRMATION_TAIL)


def card_action_for(utterance: str) -> str:
    """ "keep" to leave the card on screen, "replace" to put up a new one."""
    if is_sign_off(utterance) or is_bare_confirmation(utterance):
        return "keep"
    return "replace"
