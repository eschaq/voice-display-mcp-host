"""Caps, limits, and who the client is."""

from __future__ import annotations

from voice_display_host.guard import RateLimiter, cap, client_ip
from voice_display_host.intent import card_action_for, is_bare_confirmation, is_sign_off


def test_the_client_is_the_right_most_forwarded_entry() -> None:
    assert client_ip("203.0.113.9", "10.0.0.5") == "203.0.113.9"


def test_a_spoofed_left_hand_entry_is_ignored() -> None:
    """A client can send its own header and a proxy appends rather than
    replaces, so reading from the left lets an attacker pick their own
    bucket and get a fresh one every request."""
    spoofed = "1.1.1.1, 2.2.2.2, 203.0.113.9"
    assert client_ip(spoofed, "10.0.0.5") == "203.0.113.9"


def test_an_extra_trusted_hop_skips_one_from_the_right() -> None:
    assert client_ip("203.0.113.9, 198.51.100.7", "10.0.0.5", hops=1) == "203.0.113.9"


def test_no_header_falls_back_to_the_peer() -> None:
    assert client_ip(None, "10.0.0.5") == "10.0.0.5"
    assert client_ip(None, None) == "unknown"


def test_the_limiter_allows_the_allowance_and_then_refuses() -> None:
    limiter = RateLimiter(per_minute=3)
    assert [limiter.allow("v", now=1.0) for _ in range(3)] == [True, True, True]
    assert limiter.allow("v", now=1.0) is False


def test_the_window_slides() -> None:
    limiter = RateLimiter(per_minute=1)
    assert limiter.allow("v", now=0.0) is True
    assert limiter.allow("v", now=30.0) is False
    assert limiter.allow("v", now=61.0) is True


def test_one_visitor_does_not_spend_anothers_allowance() -> None:
    limiter = RateLimiter(per_minute=1)
    assert limiter.allow("alice", now=0.0) is True
    assert limiter.allow("bob", now=0.0) is True


def test_an_utterance_is_trimmed_rather_than_refused() -> None:
    assert cap("x" * 900, 500) == "x" * 500
    assert cap(None, 10) == ""


# --- intent -------------------------------------------------------------


def test_a_bare_yes_keeps_the_card() -> None:
    for said in ("Yes", "yes please", "Okay", "do it", "sure", "go ahead"):
        assert is_bare_confirmation(said), said
        assert card_action_for(said) == "keep"


def test_a_yes_with_a_question_after_it_is_a_question() -> None:
    said = "Yes. And why was it late?"
    assert is_bare_confirmation(said) is False
    assert card_action_for(said) == "replace"


def test_a_sign_off_keeps_what_is_on_screen() -> None:
    for said in ("that's it", "I'm done", "no thanks", "stop"):
        assert is_sign_off(said), said
        assert card_action_for(said) == "keep"


def test_a_sign_off_prefix_is_not_a_sign_off() -> None:
    """ "That's it for the blue one, what about the red?" is a question,
    and answering it with goodbye would be the rudest bug in the product."""
    assert is_sign_off("that's it for the blue one, what about the red?") is False
