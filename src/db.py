from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from pgvector.psycopg import register_vector

from src.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)


if engine.dialect.name == "postgresql":
    @event.listens_for(engine, "connect")
    def _register_pgvector_types(dbapi_connection, _connection_record) -> None:
        """Teach Psycopg how to bind pgvector/halfvec values on every pooled connection."""
        register_vector(dbapi_connection)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
