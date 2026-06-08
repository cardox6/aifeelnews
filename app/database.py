from datetime import datetime
from typing import Any, Generator, Optional

from sqlalchemy import DateTime, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base using Mapped[] annotation style."""

    # Map every Mapped[datetime] to a timezone-aware column. All migrations
    # already create `timestamptz`, but the bare Mapped[datetime] default maps
    # to TIMESTAMP WITHOUT TIME ZONE — so `alembic revision --autogenerate`
    # would emit a spurious tz-stripping migration. Aligning the model with the
    # real schema here (one place) removes that footgun. SQLite ignores the
    # timezone flag, so the test fixtures are unaffected.
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


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
    # pool_pre_ping detects connections killed by Cloud SQL idle-timeout
    # before SQLAlchemy hands them to a request; pool_recycle forces a
    # refresh every hour so long-lived idle pools don't hit DB-side TTLs.
    #
    # Pool sized explicitly against the deployment, not left at the SQLAlchemy
    # default (5 + 10 = 15/instance). Cloud SQL caps max_connections at 50
    # (infra/main.tf), and max-instances=10 web + the ingestion/crawl/ttl jobs
    # all draw from this same config, so the default 15/instance (150 at full
    # scale-out) would over-subscribe the DB. 4/instance keeps the web fleet at
    # 40 worst-case, leaving headroom for jobs + Postgres' reserved slots.
    # pool_timeout=10 fails fast instead of the silent 30s default.
    _engine = create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=2,
        max_overflow=2,
        pool_timeout=10,
    )
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
