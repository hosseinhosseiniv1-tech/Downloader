"""SSRF-safe URL validation and filename sanitisation.

Threat model:
- We accept user-supplied URLs and pass them to yt-dlp, which will make
  outbound requests. Without a guard, an attacker can force our worker to
  hit ``http://169.254.169.254/`` (cloud metadata), ``http://localhost/``,
  RFC 1918 ranges, or IPv6 unique-local / link-local addresses.
- We therefore resolve the hostname to *all* of its A/AAAA records and
  reject if *any* address is private, loopback, link-local, reserved, or
  multicast. We also refuse non-HTTP(S) schemes and hostnames without a
  dot (e.g. ``metadata``) unless explicitly whitelisted.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urlsplit

from .errors import ErrorCode, Result, err, ok

# Schemes we permit. Note: ``file://`` is deliberately excluded.
_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that we always reject regardless of what DNS resolves them to.
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
        "metadata.azure.internal",
    }
)

# Suffixes that we always reject (private RFC 6762 mDNS, AWS metadata, etc.).
_BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".internal",
    ".local",
    ".home.arpa",
)

# Characters unsafe in filenames on POSIX + Windows + Telegram constraints.
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
_MAX_FILENAME_LEN = 120


def validate_url(url: str) -> Result:
    """Validate a user-supplied URL against the SSRF policy.

    Returns:
        ``{"ok": True, "data": {"url": <normalised>, "scheme": ..., "host": ...}}``
        or a structured error describing *why* the URL was rejected.
    """
    if not isinstance(url, str) or not url.strip():
        return err(ErrorCode.INVALID_URL, "URL is empty.")
    if len(url) > 4096:
        return err(ErrorCode.INVALID_URL, "URL is longer than 4096 characters.")

    url = url.strip()
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        return err(ErrorCode.INVALID_URL, f"Could not parse URL: {exc}")

    scheme = (parts.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return err(
            ErrorCode.UNSUPPORTED_SCHEME,
            f"Scheme '{scheme or '<none>'}' is not supported. Use http or https.",
        )

    host = (parts.hostname or "").strip().lower()
    if not host:
        return err(ErrorCode.INVALID_URL, "URL is missing a hostname.")

    if host in _BLOCKED_HOSTNAMES:
        return err(ErrorCode.UNSAFE_URL, "Refusing to access internal hostname.")
    if any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        return err(ErrorCode.UNSAFE_URL, "Refusing to access internal hostname.")

    # Reject single-label hostnames like ``localhost`` or ``metadata`` — public
    # sites on the internet always have at least one dot (or are IP literals).
    try:
        ipaddress.ip_address(host)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if not is_ip_literal and "." not in host:
        return err(ErrorCode.UNSAFE_URL, "Single-label hostnames are not allowed.")

    # If the host is an IP literal, check it directly.
    if is_ip_literal:
        ip = ipaddress.ip_address(host)
        if _ip_is_unsafe(ip):
            return err(ErrorCode.UNSAFE_URL, "Refusing to access private IP address.")
        return ok({"url": url, "scheme": scheme, "host": host})

    # Otherwise resolve and check *every* A/AAAA record.
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        return err(ErrorCode.DNS_LOOKUP_FAILED, f"DNS lookup failed for {host}: {exc}")

    resolved: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        addr = sockaddr[0]
        resolved.append(addr)
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if _ip_is_unsafe(ip):
            return err(
                ErrorCode.UNSAFE_URL,
                f"Hostname {host} resolves to a private/loopback address ({addr}).",
            )

    if not resolved:
        return err(ErrorCode.DNS_LOOKUP_FAILED, f"Hostname {host} did not resolve to any address.")

    return ok({"url": url, "scheme": scheme, "host": host, "resolved": sorted(set(resolved))})


def is_safe_url(url: str) -> bool:
    """Convenience boolean wrapper around :func:`validate_url`."""
    return bool(validate_url(url).get("ok"))


def _ip_is_unsafe(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if ``ip`` is loopback / private / link-local / reserved."""
    # IPv4-mapped IPv6 (::ffff:127.0.0.1) must be checked as IPv4.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _ip_is_unsafe(ip.ipv4_mapped)

    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe filename derived from ``name``.

    Guarantees:
    - Non-empty.
    - No path separators or Windows-reserved characters.
    - Not ``.`` or ``..``.
    - Length <= 120 chars.
    - Does not end with a dot or space (Windows).
    """
    if not isinstance(name, str):
        name = str(name)
    name = name.strip()

    # Collapse whitespace, drop control chars and unsafe symbols.
    name = re.sub(r"\s+", " ", name)
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)

    # Defeat path traversal and empty names.
    name = name.lstrip(".-")
    name = name.rstrip(". ")

    if not name or name in {".", ".."}:
        name = "download"

    if len(name) > _MAX_FILENAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and len(ext) <= 10:
            keep = _MAX_FILENAME_LEN - len(ext) - 1
            name = f"{stem[:keep]}.{ext}"
        else:
            name = name[:_MAX_FILENAME_LEN]

    return name


def _debug_result(url: str) -> dict[str, Any]:  # pragma: no cover - debugging aid
    """Internal helper — returns the raw validation result for logging."""
    return dict(validate_url(url))