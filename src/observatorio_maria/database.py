from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from observatorio_maria.settings import Settings

settings = Settings()


def enable_sqlite_foreign_keys(engine: AsyncEngine):
    """O SQLite só aplica ON DELETE CASCADE com foreign_keys ligado."""
    if engine.dialect.name != 'sqlite':
        return

    @event.listens_for(engine.sync_engine, 'connect')
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


engine = create_async_engine(settings.DATABASE_URL)
enable_sqlite_foreign_keys(engine)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session
