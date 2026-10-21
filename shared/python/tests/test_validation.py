"""Unit tests for SSRF guards and filename sanitisation."""

from __future__ import annotations

import pytest

from download_core.errors import ErrorCode
from download_core.validation import is_safe_url, sanitize_filename, validate_url


# ---------------------------------------------------------------------------
# URL validation / SSRF guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not a url",
        "ftp://example.com/video",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "gopher://example.com",
    ],
)
def test_validate_url_rejects_bad_inputs(url: str):
    result = validate_url(url)
    assert result["ok"] is False


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "https://localhost/",
        "http://127.0.0.1/",
        "http://127.0.0.2/",
        "http://0.0.0.0/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fc00::1]/",
        "http://metadata.google.internal/",
        "http://metadata.azure.internal/",
        "http://something.local/",
        "http://something.internal/",
    ],
)
def test_validate_url_blocks_internal_targets(url: str):
    result = validate_url(url)
    assert result["ok"] is False
    assert result["error_code"] in {
        ErrorCode.UNSAFE_URL,
        ErrorCode.INVALID_URL,
        ErrorCode.UNSUPPORTED_SCHEME,
        ErrorCode.DNS_LOOKUP_FAILED,
    }


def test_validate_url_rejects_single_label_hostname():
    result = validate_url("http://intranet/")
    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.UNSAFE_URL


def test_validate_url_rejects_empty_url():
    result = validate_url("")
    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.INVALID_URL


def test_validate_url_rejects_overlong_url():
    result = validate_url("https://example.com/" + ("a" * 5000))
    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.INVALID_URL


def test_validate_url_accepts_public_https(monkeypatch: pytest.MonkeyPatch):
    # Patch DNS so the test is hermetic and offline-safe.
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
        ]

    monkeypatch.setattr("download_core.validation.socket.getaddrinfo", fake_getaddrinfo)
    result = validate_url("https://example.com/watch?v=abc")
    assert result["ok"] is True
    assert result["data"]["host"] == "example.com"
    assert "93.184.216.34" in result["data"]["resolved"]


def test_validate_url_rejects_host_resolving_to_private(monkeypatch: pytest.MonkeyPatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
        ]

    monkeypatch.setattr("download_core.validation.socket.getaddrinfo", fake_getaddrinfo)
    result = validate_url("https://evil.example.com/")
    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.UNSAFE_URL


def test_validate_url_rejects_private_v6(monkeypatch: pytest.MonkeyPatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fc00::1", port, 0, 0)),
        ]

    monkeypatch.setattr("download_core.validation.socket.getaddrinfo", fake_getaddrinfo)
    result = validate_url("https://v6.example.com/")
    assert result["ok"] is False
    assert result["error_code"] == ErrorCode.UNSAFE_URL


def test_is_safe_url_wrapper(monkeypatch: pytest.MonkeyPatch):
    import socket

    monkeypatch.setattr(
        "download_core.validation.socket.getaddrinfo",
        lambda h, p, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", p))],
    )
    assert is_safe_url("https://ok.example.com/") is True
    assert is_safe_url("http://127.0.0.1/") is False


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("simple.mp4", "simple.mp4"),
        ("with spaces.mp4", "with spaces.mp4"),
        ("../../etc/passwd", "etc_passwd"),
        ("..", "download"),
        (".", "download"),
        ("", "download"),
        ("   ", "download"),
        ('bad<>:"|?*chars', "bad_______chars"),
        ("trailing...", "trailing"),
        ("newline\nname", "newline_name"),
        ("tab\there", "tab here"),
        ("a" * 200, "a" * 120),
        ("video." + "b" * 200 + ".mp4", "video." + "b" * 98 + ".mp4"),
    ],
)
def test_sanitize_filename_cases(raw: str, expected: str):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_non_string():
    assert sanitize_filename(12345) == "12345"