"""Global error handler — never leaks stack traces to users."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import ErrorEvent

from download_core.logging import get_logger, new_correlation_id

log = get_logger("bot.errors")

router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    correlation_id = new_correlation_id("err")
    exc = event.exception
    log.error(
        "bot.unhandled_exception",
        correlation_id=correlation_id,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )

    update = event.update
    try:
        if update.message:
            await update.message.answer(
                "⚠️ Something went wrong. Please try again.\n"
                f"<code>ref: {correlation_id}</code>"
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "⚠️ Something went wrong. Please try again.",
                show_alert=False,
            )
    except Exception as secondary:
        log.warning(
            "bot.error_notify_failed",
            correlation_id=correlation_id,
            error=str(secondary),
        )
    return True  # suppress further propagation