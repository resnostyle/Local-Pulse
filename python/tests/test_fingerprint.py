"""Tests for fingerprint generation."""

import pytest

from db.fingerprint import compute_fingerprint


def test_compute_fingerprint_returns_64_char_hex():
    fp = compute_fingerprint("Test Event", "2026-03-15T14:00:00Z", "https://example.com/1")
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_compute_fingerprint_deterministic():
    fp1 = compute_fingerprint("Same Event", "2026-03-15", "https://example.com")
    fp2 = compute_fingerprint("Same Event", "2026-03-15", "https://example.com")
    assert fp1 == fp2


def test_compute_fingerprint_different_inputs_different_outputs():
    fp1 = compute_fingerprint("Event A", "2026-03-15", "https://a.com")
    fp2 = compute_fingerprint("Event B", "2026-03-15", "https://a.com")
    fp3 = compute_fingerprint("Event A", "2026-03-16", "https://a.com")
    fp4 = compute_fingerprint("Event A", "2026-03-15", "https://b.com")
    assert len({fp1, fp2, fp3, fp4}) == 4
