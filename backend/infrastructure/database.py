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


def _migrate_reservation_guest_fields() -> None:
    """Add reservation_for, staying_person_count, primary/secondary guest columns; backfill legacy rows."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    with engine.connect() as conn:
        if "reservation_for" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE reservation_request ADD COLUMN reservation_for VARCHAR(20) DEFAULT 'SELF'"
                )
            )
            conn.commit()
        if "staying_person_count" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE reservation_request ADD COLUMN staying_person_count INTEGER DEFAULT 1"
                )
            )
            conn.commit()
        if "primary_guest_name" not in cols:
            conn.execute(text("ALTER TABLE reservation_request ADD COLUMN primary_guest_name VARCHAR(255)"))
            conn.commit()
        if "primary_guest_email" not in cols:
            conn.execute(text("ALTER TABLE reservation_request ADD COLUMN primary_guest_email VARCHAR(255)"))
            conn.commit()
        if "secondary_guest_name" not in cols:
            conn.execute(
                text("ALTER TABLE reservation_request ADD COLUMN secondary_guest_name VARCHAR(255)")
            )
            conn.commit()
        if "secondary_guest_email" not in cols:
            conn.execute(
                text("ALTER TABLE reservation_request ADD COLUMN secondary_guest_email VARCHAR(255)")
            )
            conn.commit()
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE reservation_request SET reservation_for = 'SELF' "
                "WHERE reservation_for IS NULL OR TRIM(COALESCE(reservation_for, '')) = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE reservation_request SET staying_person_count = 1 "
                "WHERE staying_person_count IS NULL"
            )
        )
        conn.execute(
            text(
                "UPDATE reservation_request SET primary_guest_name = requester_name "
                "WHERE primary_guest_name IS NULL OR TRIM(COALESCE(primary_guest_name, '')) = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE reservation_request SET primary_guest_email = requester_email "
                "WHERE primary_guest_email IS NULL OR TRIM(COALESCE(primary_guest_email, '')) = ''"
            )
        )
        conn.commit()
    logger.info("Migration: reservation_request guest / occupancy fields ensured")


def _migrate_guest_fields_coherence() -> None:
    """Align stored guest rows with app rules: SELF primary = requester; single occupancy has no second guest."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    needed = {
        "reservation_for",
        "staying_person_count",
        "primary_guest_name",
        "primary_guest_email",
        "secondary_guest_name",
        "secondary_guest_email",
        "requester_name",
        "requester_email",
    }
    if not needed.issubset(cols):
        return
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE reservation_request SET secondary_guest_name = NULL, "
                "secondary_guest_email = NULL "
                "WHERE COALESCE(staying_person_count, 1) = 1"
            )
        )
        conn.execute(
            text(
                "UPDATE reservation_request SET primary_guest_name = TRIM(requester_name), "
                "primary_guest_email = LOWER(TRIM(requester_email)) "
                "WHERE reservation_for IS NULL OR TRIM(COALESCE(reservation_for, '')) = '' "
                "OR reservation_for = 'SELF'"
            )
        )
        conn.commit()
    logger.info("Migration: guest fields coherence (SELF primary, clear second when 1 person)")


def _migrate_reception_internal_note() -> None:
    """Add reception-only internal note column (never exposed on employee APIs)."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    if "reception_internal_note" in cols:
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE reservation_request ADD COLUMN reception_internal_note TEXT")
        )
        conn.commit()
    logger.info("Migration: added reservation_request.reception_internal_note")


def _migrate_pending_change_request() -> None:
    """Pending employee change request (single active JSON payload + timestamp)."""
    engine = get_engine()
    insp = inspect(engine)
    if not insp.has_table("reservation_request"):
        return
    cols = {c["name"] for c in insp.get_columns("reservation_request")}
    with engine.connect() as conn:
        if "pending_change_submitted_at" not in cols:
            conn.execute(
                text("ALTER TABLE reservation_request ADD COLUMN pending_change_submitted_at DATETIME")
            )
            conn.commit()
        if "pending_change_json" not in cols:
            conn.execute(
                text("ALTER TABLE reservation_request ADD COLUMN pending_change_json TEXT")
            )
            conn.commit()
    logger.info("Migration: reservation_request pending change columns ensured")


def init_db() -> None:
    # Import models so SQLModel registers metadata
    from infrastructure import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
    _migrate_add_reservation_user_id()
    _migrate_reservation_urgency_and_booking_flag()
    _migrate_reservation_guest_fields()
    _migrate_guest_fields_coherence()
    _migrate_reception_internal_note()
    _migrate_pending_change_request()
    from application.auth_service import seed_bootstrap_users

    with Session(get_engine()) as session:
        seed_bootstrap_users(session)
    logger.info("Database tables ensured")


def get_session():
    with Session(get_engine()) as session:
        yield session
