import logging
import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger(__name__)

_engine = None


def _default_sqlite_url() -> str:
    """File DB in backend folder for local dev when DATABASE_URL is unset."""
    backend_root = Path(__file__).resolve().parent.parent
    db_file = backend_root / "hotel_local.db"
    # Windows-safe absolute URL for SQLAlchemy (e.g. sqlite:///C:/path/to.db)
    return "sqlite:///" + db_file.resolve().as_posix()


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    logger.info("DATABASE_URL not set; using local SQLite (hotel_local.db)")
    return _default_sqlite_url()


def get_engine():
    global _engine
    if _engine is None:
        url = get_database_url()
        kwargs = {"echo": False}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        logger.debug("SQLAlchemy engine created")
    return _engine


def _migrate_add_reservation_user_id() -> None:
    """Add user_id to reservation_request on existing DBs (create_all does not alter tables)."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    if "user_id" in cols:
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE reservation_request ADD COLUMN user_id VARCHAR(36)"))
        conn.commit()
    logger.info("Migration: added reservation_request.user_id")


def _migrate_reservation_urgency_and_booking_flag() -> None:
    """Add urgency, urgency_reason, was_ever_booked; backfill legacy rows."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    with engine.connect() as conn:
        if "urgency" not in cols:
            conn.execute(text("ALTER TABLE reservation_request ADD COLUMN urgency VARCHAR(20)"))
            conn.commit()
        if "urgency_reason" not in cols:
            conn.execute(text("ALTER TABLE reservation_request ADD COLUMN urgency_reason VARCHAR(500)"))
            conn.commit()
        if "was_ever_booked" not in cols:
            conn.execute(
                text("ALTER TABLE reservation_request ADD COLUMN was_ever_booked BOOLEAN DEFAULT 0")
            )
            conn.commit()
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE reservation_request SET urgency = 'STANDARD' "
                "WHERE urgency IS NULL OR TRIM(COALESCE(urgency, '')) = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE reservation_request SET was_ever_booked = 1 "
                "WHERE status = 'BOOKED' OR (COALESCE(TRIM(reservation_number), '') != '')"
            )
        )
        conn.commit()
    logger.info("Migration: reservation_request urgency / was_ever_booked ensured")


def init_db() -> None:
    # Import models so SQLModel registers metadata
    from infrastructure import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
    _migrate_add_reservation_user_id()
    _migrate_reservation_urgency_and_booking_flag()
    from application.auth_service import seed_bootstrap_users

    with Session(get_engine()) as session:
        seed_bootstrap_users(session)
    logger.info("Database tables ensured")


def get_session():
    with Session(get_engine()) as session:
        yield session
