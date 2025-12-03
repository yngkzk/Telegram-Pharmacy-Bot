import asyncio
from aiogram import Router, types
from aiogram.filters import ExceptionTypeFilter
from aiogram.types.error_event import ErrorEvent
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError
)

from utils.logger.logger_config import logger

# Create a separate router for errors (Best Practice)
router = Router()


def setup_error_handler(dp):
    """
    Registers the error handler router to the dispatcher.
    """
    dp.include_router(router)


# ============================================================
# 1. IGNORE HARMLESS ERRORS
# ============================================================
@router.error(ExceptionTypeFilter(TelegramBadRequest))
async def handle_bad_request(event: ErrorEvent):
    """
    Handles 'Message is not modified' and other bad requests.
    """
    exc = event.exception

    # Common error when clicking a button that doesn't change content
    if "message is not modified" in str(exc).lower():
        logger.debug("Message not modified (harmless)")
        return  # Do nothing

    logger.warning(f"⚠️ Telegram Bad Request: {exc}")


# ============================================================
# 2. HANDLE BOT BLOCKED (Forbidden)
# ============================================================
@router.error(ExceptionTypeFilter(TelegramForbiddenError))
async def handle_forbidden(event: ErrorEvent):
    """
    User blocked the bot.
    """
    logger.info(f"User blocked the bot. Update: {event.update}")


# ============================================================
# 3. HANDLE CRITICAL UNKNOWN ERRORS
# ============================================================
@router.error()
async def handle_unknown_error(event: ErrorEvent):
    """
    Catch-all for any other crashes (DB errors, Logic bugs).
    """
    exc = event.exception
    update = event.update

    logger.error(f"❌ Unhandled Error: {exc}", exc_info=True)

    # Try to notify the user so they aren't left wondering
    try:
        if update.callback_query:
            await update.callback_query.answer("⚠️ Произошла ошибка. Попробуйте позже.", show_alert=True)
        elif update.message:
            await update.message.answer("⚠️ Произошла внутренняя ошибка. Мы уже работаем над этим.")
    except Exception:
        # If we can't even send a message, just give up
        pass