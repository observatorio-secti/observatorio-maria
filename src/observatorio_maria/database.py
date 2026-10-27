from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from observatorio_maria.settings import Settings

settings = Settings()


def configure_sqlite(engine: AsyncEngine):
    """Liga foreign_keys, sem o qual o SQLite ignora ON DELETE CASCADE, e o
    WAL, que deixa as leituras seguirem durante uma escrita."""
    if engine.dialect.name != 'sqlite':
        return

    @event.listens_for(engine.sync_engine, 'connect')
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()


engine = create_async_engine(settings.DATABASE_URL)
configure_sqlite(engine)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session
