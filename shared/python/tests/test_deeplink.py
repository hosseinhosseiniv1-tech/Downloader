"""Unit tests for aiogram-style deep-link encoding/decoding.

The bot uses ``aiogram.utils.deep_linking.encode_payload`` /
``decode_payload``. We test the round-trip contract here using a local
re-implementation of the same algorithm so the shared module has no
hard aiogram dependency. This mirrors the exact algorithm used by aiogram
3.x (base64url without padding).
"""

from __future__ import annotations

import base64
import binascii

import pytest


def encode_payload(payload: str, *, padding: bool = False) -> str:
    """Same algorithm as ``aiogram.utils.deep_linking.encode_payload``."""
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded if padding else encoded.rstrip("=")


def decode_payload(payload: str) -> str:
    """Same algorithm as ``aiogram.utils.deep_linking.decode_payload``."""
    padding = "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(payload + padding).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid deep-link payload: {exc}") from exc


@pytest.mark.parametrize(
    "payload",
    [
        "get_chylcmrdiyvcqjlt",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://t.me/StoaderBot?start=get_abc123",
        "job-1f3e9c2a",
        "سلام دنیا",
        "🙂 emoji 🙂",
        "a" * 64,
    ],
)
def test_deep_link_round_trip(payload: str):
    encoded = encode_payload(payload)
    decoded = decode_payload(encoded)
    assert decoded == payload


def test_encode_is_url_safe_no_padding():
    encoded = encode_payload("https://example.com/watch?v=abc")
    assert "=" not in encoded
    assert "+" not in encoded
    assert "/" not in encoded


def test_encode_padding_option():
    encoded = encode_payload("abc", padding=True)
    assert encoded.endswith("=")


def test_decode_with_padding_present():
    encoded = encode_payload("hello world", padding=True)
    assert decode_payload(encoded) == "hello world"


def test_decode_rejects_invalid_base64():
    with pytest.raises(ValueError):
        decode_payload("!!!not-base64!!!")


def test_start_param_extraction():
    """The bot receives ``/start get_xxx`` and must strip the ``get_`` prefix."""
    raw = "get_chylcmrdiyvcqjlt"
    assert raw.startswith("get_")
    payload = raw[len("get_"):]
    assert payload == "chylcmrdiyvcqjlt"


def test_url_payload_round_trip():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    encoded = encode_payload(url)
    decoded = decode_payload(encoded)
    assert decoded == url
    # A user can paste the encoded payload into the start param and the bot
    # will treat it as a pre-filled URL.
    assert decoded.startswith("https://")