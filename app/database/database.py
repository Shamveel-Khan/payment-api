from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for the duration of a request."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    """Verify that the application can connect to PostgreSQL."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))