"""Shared pytest fixtures for download_core."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ensure environment variables don't leak between tests."""
    for key in (
        "PROXY_URL",
        "POT_SERVER_URL",
        "COOKIES_FILE",
        "COOKIES_FROM_BROWSER",
        "YDL_VERBOSE",
        "METADATA_TIMEOUT_SECONDS",
        "DOWNLOAD_DIR",
        "YDL_OUTTMPL",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture()
def fake_cookies_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "cookies.txt"
    path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("COOKIES_FILE", str(path))
    return path