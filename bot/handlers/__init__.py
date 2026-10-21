"""Handlers package — exports a single ``register`` function."""

from __future__ import annotations

from aiogram import Dispatcher

from . import download, language, share, start


def register(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(share.router)
    dp.include_router(download.router)