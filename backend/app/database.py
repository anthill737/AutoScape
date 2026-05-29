import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./autoscape.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")
_is_memory = DATABASE_URL == "sqlite:///:memory:"

# check_same_thread=False is required because FastAPI runs sync endpoints in a
# threadpool, so a connection may be used from a different thread than created.
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)


if _is_sqlite and not _is_memory:
    # Default SQLite uses a rollback journal that locks the whole database for
    # writes, so concurrent requests (e.g. several render images loading at once
    # alongside an API read) intermittently fail with "database is locked",
    # surfacing as flaky 500s / blank images. WAL lets readers and a writer run
    # concurrently, and busy_timeout makes transient locks wait-and-retry
    # instead of erroring out.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
