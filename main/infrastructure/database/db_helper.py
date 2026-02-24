from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from utils.config.config import config

from infrastructure.database.models.base import Base
import infrastructure.database.models.users
import infrastructure.database.models.pharmacy
import infrastructure.database.models.reports

class DatabaseHelper:
    def __init__(self):
        self.engine = create_async_engine(config.url_database, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

db_helper = DatabaseHelper()