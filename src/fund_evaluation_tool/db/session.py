"""Database session management."""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_DEFAULT_DB = Path(__file__).parent.parent.parent.parent.parent / "fund_eval.db"

_engine = None
_SessionLocal = None


def init_db(db_path: str | Path = _DEFAULT_DB) -> None:
    """Initialise the database, creating tables if they don't exist."""
    global _engine, _SessionLocal
    _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)


@contextmanager
def get_session() -> Session:
    """Context manager that yields a database session."""
    if _SessionLocal is None:
        init_db()
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
