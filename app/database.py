from typing import Any, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base using Mapped[] annotation style."""

    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def _initialize() -> None:
    global _engine, _SessionLocal
    url = settings.SQLALCHEMY_DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set DATABASE_URL (production) or LOCAL_DATABASE_URL (local) "
            "before instantiating a database session."
        )
    _engine = create_engine(url, echo=False)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def __getattr__(name: str) -> Any:
    """Lazy module-level attribute resolution (PEP 562).

    Defers engine + sessionmaker creation until first access of `engine` or
    `SessionLocal`, so importing this module never requires DATABASE_URL.
    """
    if name in ("engine", "SessionLocal"):
        if _engine is None:
            _initialize()
        return _engine if name == "engine" else _SessionLocal
    raise AttributeError(f"module 'app.database' has no attribute {name!r}")


def get_db() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        _initialize()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
