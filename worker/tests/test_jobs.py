"""Unit tests for worker.jobs — focusing on upload-limit handling."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker import jobs


@pytest.mark.asyncio
async def test_upload_too_large_detected_from_413(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("LOCAL_BOT_API_URL", "http://local.test:8081")

    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 1024)

    class FakeResponse:
        status = 413
        async def text(self):
            return "RequestEntityTooLarge"
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class FakeSession:
        def post(self, *args, **kwargs):
            return FakeResponse()

    reporter = MagicMock()
    reporter.maybe_edit = AsyncMock()

    with pytest.raises(jobs.UploadTooLarge):
        await jobs._upload_file(
            FakeSession(),  # type: ignore[arg-type]
            job_id="job-x",
            chat_id=1,
            filepath=f,
            quality="best",
            title="t",
            reporter=reporter,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_upload_success_returns_result(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 1024)

    class FakeResponse:
        status = 200
        async def text(self):
            return '{"ok": true, "result": {"message_id": 42}}'
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None

    class FakeSession:
        def post(self, *args, **kwargs):
            return FakeResponse()

    reporter = MagicMock()
    reporter.maybe_edit = AsyncMock()

    result = await jobs._upload_file(
        FakeSession(),  # type: ignore[arg-type]
        job_id="job-x",
        chat_id=1,
        filepath=f,
        quality="audio",
        title="song",
        reporter=reporter,  # type: ignore[arg-type]
    )
    assert result["message_id"] == 42


def test_cleanup_deletes_old_files(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOWNLOAD_DIR", str(tmp_path))
    old = tmp_path / "old.bin"
    old.write_bytes(b"x")
    # Backdate mtime by 3 hours.
    import os, time
    three_hours_ago = time.time() - 3 * 3600
    os.utime(old, (three_hours_ago, three_hours_ago))

    fresh = tmp_path / "fresh.bin"
    fresh.write_bytes(b"y")

    report = jobs.cleanup_old_files(max_age_seconds=2 * 3600)
    assert report["deleted"] == 1
    assert not old.exists()
    assert fresh.exists()


def test_hard_limit_constant():
    assert jobs.HARD_TELEGRAM_LIMIT_BYTES == 2 * 1024 * 1024 * 1024