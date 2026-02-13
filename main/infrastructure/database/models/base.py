from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    """
    Базовый класс для всех моделей.
    AsyncAttrs нужен для lazy loading в асинхронном режиме.
    """
    __abstract__ = True