"""Idempotent seed loader for local development.

The seed dataset (``app/seeds/seed_data.json``) contains 50 articles spanning
10 sources, sampled from the production database with PII removed (``users``
and ``bookmarks`` deliberately excluded). The data shape mirrors the live
schema so it exercises the same code paths the production ingest job does.

This script is idempotent: it inserts new sources / articles, but skips
sources whose ``name`` already exists and articles whose ``url`` already
exists. Re-running it is safe.

Usage::

    # Default: insert any rows missing from the local DB.
    python -m app.seeds.seed_db

    # Wipe seed-derived rows first, then re-insert.
    # Bookmark FK CASCADE cleans up any test bookmarks that referenced
    # articles being deleted (articles -> bookmarks ON DELETE CASCADE).
    python -m app.seeds.seed_db --reset

    # Dry-run: print what would happen, no commits.
    python -m app.seeds.seed_db --dry-run

The script uses standard SQLAlchemy ORM so it works against either SQLite
(local default) or PostgreSQL (Docker / standalone).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.source import Source

DEFAULT_SEED_PATH = Path(__file__).resolve().parent / "seed_data.json"


def _parse_published_at(value: Any) -> datetime:
    """Coerce the JSON ``published_at`` value into a naive datetime.

    Accepts ISO-8601 strings (with or without trailing ``Z`` / offset). We
    strip the timezone to keep parity with the rest of the schema, which
    stores naive UTC datetimes.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        # Python <3.11 doesn't accept "Z"; replace it with +00:00.
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    else:
        raise TypeError(f"Unsupported published_at type: {type(value)!r}")

    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _load_seed(json_path: Path) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(f"Seed data not found: {json_path}")
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if "articles" not in data or "sources" not in data:
        raise ValueError(
            f"Seed file missing required keys (need 'articles' and 'sources'): {json_path}"
        )
    return data  # type: ignore[no-any-return]


def _reset_seed_rows(db: Session, data: dict[str, Any]) -> None:
    """Delete seed-derived articles and sources before re-inserting.

    Works on any backend: we use ORM-level deletes by URL/name so we don't
    rely on Postgres-specific syntax. Bookmark cascade is handled by the
    FK ON DELETE CASCADE on ``articles -> bookmarks`` and
    ``sources -> articles``.
    """
    seed_urls = [a["url"] for a in data["articles"]]
    seed_source_names = [s["name"] for s in data["sources"]]

    if seed_urls:
        db.query(Article).filter(Article.url.in_(seed_urls)).delete(
            synchronize_session=False
        )
    if seed_source_names:
        db.query(Source).filter(Source.name.in_(seed_source_names)).delete(
            synchronize_session=False
        )


def seed_database(
    db: Session,
    json_path: Optional[Path] = None,
    *,
    reset: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    """Seed the database from ``seed_data.json``.

    Returns a summary dict with keys::

        {
            "sources_inserted": int,
            "sources_skipped": int,
            "articles_inserted": int,
            "articles_skipped": int,
        }

    On ``dry_run=True``, no INSERT/DELETE is committed; counts reflect what
    *would* have been inserted.
    """
    path = json_path or DEFAULT_SEED_PATH
    data = _load_seed(path)

    if reset and not dry_run:
        _reset_seed_rows(db, data)
        db.flush()

    sources_inserted = 0
    sources_skipped = 0
    source_id_by_name: dict[str, int] = {}

    for src in data["sources"]:
        name = src["name"]
        existing = db.query(Source).filter_by(name=name).first()
        if existing is not None:
            source_id_by_name[name] = existing.id
            sources_skipped += 1
            continue

        new_src = Source(name=name)
        db.add(new_src)
        db.flush()  # populate id
        source_id_by_name[name] = new_src.id
        sources_inserted += 1

    articles_inserted = 0
    articles_skipped = 0
    seen_urls_in_batch: set[str] = set()

    for art in data["articles"]:
        url = art["url"]
        if url in seen_urls_in_batch:
            articles_skipped += 1
            continue
        if db.query(Article).filter_by(url=url).first() is not None:
            articles_skipped += 1
            seen_urls_in_batch.add(url)
            continue

        source_name = art["source_name"]
        source_id = source_id_by_name.get(source_name)
        if source_id is None:
            # Article references a source not declared in the sources block;
            # create-on-the-fly so we don't lose the row.
            existing_src = db.query(Source).filter_by(name=source_name).first()
            if existing_src is None:
                fallback_src = Source(name=source_name)
                db.add(fallback_src)
                db.flush()
                source_id = fallback_src.id
                sources_inserted += 1
            else:
                source_id = existing_src.id
            source_id_by_name[source_name] = source_id

        db.add(
            Article(
                title=art["title"],
                description=art["description"],
                url=url,
                image_url=art["image_url"],
                published_at=_parse_published_at(art["published_at"]),
                language=art["language"],
                country=art["country"],
                category=art["category"],
                sentiment_label=art["sentiment_label"],
                sentiment_score=art["sentiment_score"],
                source_id=source_id,
            )
        )
        seen_urls_in_batch.add(url)
        articles_inserted += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "sources_inserted": sources_inserted,
        "sources_skipped": sources_skipped,
        "articles_inserted": articles_inserted,
        "articles_skipped": articles_skipped,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed the local database with sample articles + sources. Idempotent: "
            "re-running skips rows that already exist."
        )
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Delete seed-derived articles and sources before re-inserting. "
            "Bookmark FK CASCADE will clean up any test bookmarks that "
            "reference articles being removed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without committing any changes.",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=None,
        help="Path to seed JSON (defaults to app/seeds/seed_data.json).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    # Imported lazily so ``--help`` doesn't require DATABASE_URL to be set.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        summary = seed_database(
            db,
            json_path=args.json_path,
            reset=args.reset,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        db.rollback()
        print(f"ERROR: seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    prefix = "[dry-run] " if args.dry_run else ""
    print(
        f"{prefix}Seeded {summary['sources_inserted']} new sources, "
        f"{summary['articles_inserted']} new articles. "
        f"{summary['articles_skipped']} articles already present (skipped)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
