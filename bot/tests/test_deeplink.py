from __future__ import annotations

import base64

from bot.handlers.start import _decode_start_payload
from bot.handlers.share import _encode_payload


def test_roundtrip_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    encoded = _encode_payload(url)
    decoded = _decode_start_payload(f"get_{encoded}")
    assert decoded == url


def test_raw_url_passthrough():
    url = "https://example.com/v.mp4"
    assert _decode_start_payload(url) == url


def test_invalid_payload_returns_none():
    assert _decode_start_payload("get_!!!notbase64") is None


def test_empty_payload():
    assert _decode_start_payload("") is None


def test_base64_padding_required():
    url = "abc"  # len 3 → encoded len 4 with one '='
    encoded = _encode_payload(url)
    # ``_decode_start_payload`` re-adds padding.
    assert _decode_start_payload(encoded) == url