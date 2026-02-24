from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.report_repo import ReportRepository


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        async with db_helper.session_factory() as session:
            data["user_repo"] = UserRepository(session)
            data["pharmacy_repo"] = PharmacyRepository(session)
            data["reports_db"] = ReportRepository(session)

            return await handler(event, data)