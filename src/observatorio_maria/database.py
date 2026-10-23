from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from observatorio_maria.settings import Settings

settings = Settings()

connect_args = (
    {'check_same_thread': False}
    if settings.DATABASE_URL.startswith('sqlite')
    else {}
)

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)


def get_session():
    with Session(engine) as session:
        yield session
