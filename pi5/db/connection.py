"""Database engine, session factory and helpers."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

try:
    from config import DATABASE_URL
except ImportError:  # pragma: no cover
    from pi5.config import DATABASE_URL


# ``future=True`` keeps SQLAlchemy 2.0 semantics explicit.
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def get_session():
    """Context manager yielding a session with commit/rollback handling."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Create all tables (idempotent). Use Alembic for real migrations."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    # Smoke test against an in-memory SQLite DB so it runs without Postgres.
    from sqlalchemy import create_engine as _ce

    test_engine = _ce("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=test_engine)
    print("Created tables:", list(Base.metadata.tables.keys()))
