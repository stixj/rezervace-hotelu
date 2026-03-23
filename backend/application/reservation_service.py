import logging
import os
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from infrastructure.email import send_email
from infrastructure.models import (
    BedPreference,
    RequestStatus,
    RequestUrgency,
    ReservationFor,
    ReservationRequest,
    RoomType,
    User,
)
from schemas.reservation import (
    AdminReservationRead,
    ReceptionInternalNoteBody,
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
    StatusUpdateBody,
)

logger = logging.getLogger(__name__)


def _enum_str(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _reservation_read_from_row(row: ReservationRequest) -> ReservationRead:
    """Build API read model with coherent guest fields (SELF = podavatel; 1 osoba = bez druhé)."""
    read = ReservationRead.model_validate(row)
    updates: dict = {}
    if read.reservation_for == ReservationFor.SELF:
        updates["primary_guest_name"] = read.requester_name.strip()
        updates["primary_guest_email"] = _normalize_email(read.requester_email)
    if read.staying_person_count == 1:
        updates["secondary_guest_name"] = None
        updates["secondary_guest_email"] = None
    return read.model_copy(update=updates) if updates else read


def _admin_reservation_read_from_row(row: ReservationRequest) -> AdminReservationRead:
    base = _reservation_read_from_row(row)
    return AdminReservationRead.model_validate(
        {**base.model_dump(), "reception_internal_note": row.reception_internal_note}
    )


def _reception_recipients() -> List[str]:
    raw = os.getenv("RECEPTION_EMAIL", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def _notify_reception_safe(subject: str, body: str) -> None:
    for to in _reception_recipients():
        try:
            send_email(to, subject, body)
        except Exception:
            logger.exception("Failed to send reception email to=%s", to)


def _notify_employee_safe(to: str, subject: str, body: str) -> None:
    try:
        send_email(to, subject, body)
    except Exception:
        logger.exception("Failed to send employee email to=%s", to)


def _normalize_row_guest_fields(row: ReservationRequest) -> None:
    """Keep primary guest in sync for SELF; clear second guest when count is 1; validate."""
    if row.staying_person_count not in (1, 2):
        raise HTTPException(status_code=400, detail="staying_person_count must be 1 or 2")

    if row.reservation_for == ReservationFor.SELF:
        row.primary_guest_name = row.requester_name.strip()
        row.primary_guest_email = _normalize_email(row.requester_email)
    else:
        pn = (row.primary_guest_name or "").strip()
        pe = (row.primary_guest_email or "").strip()
        if not pn or not pe:
            raise HTTPException(
                status_code=400,
                detail="Hlavní ubytovaná osoba: vyplňte jméno i e-mail.",
            )
        row.primary_guest_name = pn
        row.primary_guest_email = _normalize_email(pe)

    if row.staying_person_count == 1:
        row.secondary_guest_name = None
        row.secondary_guest_email = None
    else:
        sn = (row.secondary_guest_name or "").strip()
        se = (row.secondary_guest_email or "").strip()
        if not sn or not se:
            raise HTTPException(
                status_code=400,
                detail="Druhá ubytovaná osoba: vyplňte jméno i e-mail.",
            )
        row.secondary_guest_name = sn
        row.secondary_guest_email = _normalize_email(se)


def _apply_bed_preference_rules(
    room_type: RoomType, bed_preference: BedPreference | None
) -> None:
    if room_type == RoomType.SINGLE and bed_preference is not None:
        raise HTTPException(
            status_code=400,
            detail="bed_preference must be null when room_type is single",
        )


def _ensure_employee_owns(row: ReservationRequest, user: User) -> None:
    if row.user_id is None or row.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed to access this reservation")


def create_reservation(session: Session, data: ReservationCreate, user: User) -> ReservationRead:
    _apply_bed_preference_rules(data.room_type, data.bed_preference)
    if data.reservation_for == ReservationFor.SELF:
        primary_name = data.requester_name.strip()
        primary_email = _normalize_email(user.email)
    else:
        primary_name = data.primary_guest_name or ""
        primary_email = data.primary_guest_email or ""
    row = ReservationRequest(
        user_id=user.id,
        requester_name=data.requester_name.strip(),
        requester_email=_normalize_email(user.email),
        reservation_for=data.reservation_for,
        staying_person_count=data.staying_person_count,
        primary_guest_name=primary_name,
        primary_guest_email=primary_email,
        secondary_guest_name=data.secondary_guest_name,
        secondary_guest_email=data.secondary_guest_email,
        city=data.city,
        date_from=data.date_from,
        date_to=data.date_to,
        room_type=data.room_type,
        bed_preference=data.bed_preference,
        note=data.note,
        urgency=data.urgency,
        urgency_reason=data.urgency_reason,
        status=RequestStatus.NEW,
    )
    _normalize_row_guest_fields(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation created id=%s user_id=%s", row.id, row.user_id)

    occ_line = f"Počet ubytovaných osob: {row.staying_person_count}\n"
    for_line = (
        "Rezervace pro: mně\n"
        if row.reservation_for == ReservationFor.SELF
        else "Rezervace pro: jiného kolegu\n"
    )
    guest_lines = (
        f"Hlavní ubytovaná: {row.primary_guest_name} <{row.primary_guest_email}>\n"
    )
    if row.staying_person_count == 2 and row.secondary_guest_name:
        guest_lines += (
            f"Druhá osoba: {row.secondary_guest_name} <{row.secondary_guest_email}>\n"
        )
    body = (
        f"Nový požadavek na rezervaci.\n"
        f"ID: {row.id}\n"
        f"Žadatel: {row.requester_name} <{row.requester_email}>\n"
        f"{for_line}"
        f"{occ_line}"
        f"{guest_lines}"
        f"Město: {_enum_str(row.city)}\n"
        f"Termín: {row.date_from} – {row.date_to}\n"
        f"Typ pokoje: {_enum_str(row.room_type)}\n"
    )
    if row.urgency == RequestUrgency.URGENT:
        body += f"Urgence: urgentní\nDůvod: {row.urgency_reason}\n"
    _notify_reception_safe(f"[Hotel] Nový požadavek {row.id}", body)
    return _reservation_read_from_row(row)


def list_my_reservations(session: Session, user: User) -> List[ReservationRead]:
    rows = session.exec(
        select(ReservationRequest)
        .where(col(ReservationRequest.user_id) == user.id)
        .order_by(ReservationRequest.created_at.desc())
    ).all()
    return [_reservation_read_from_row(r) for r in rows]


def get_reservation_for_employee(session: Session, reservation_id: UUID, user: User) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    _ensure_employee_owns(row, user)
    return _reservation_read_from_row(row)


def update_reservation(
    session: Session, reservation_id: UUID, data: ReservationUpdate, user: User
) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    _ensure_employee_owns(row, user)
    if row.status == RequestStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Reservation is cancelled")
    if row.status == RequestStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Reservation is already booked")
    if row.status == RequestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail="Žádost ve stavu „V řešení“ nelze upravovat.",
        )

    final_rt = data.room_type if data.room_type is not None else row.room_type
    if final_rt == RoomType.SINGLE:
        final_bed = None
    else:
        final_bed = (
            data.bed_preference if data.bed_preference is not None else row.bed_preference
        )
    _apply_bed_preference_rules(final_rt, final_bed)

    if data.requester_name is not None:
        row.requester_name = data.requester_name.strip()
    if data.reservation_for is not None:
        row.reservation_for = data.reservation_for
    if data.staying_person_count is not None:
        row.staying_person_count = data.staying_person_count
    if data.primary_guest_name is not None:
        row.primary_guest_name = data.primary_guest_name.strip()
    if data.primary_guest_email is not None:
        row.primary_guest_email = data.primary_guest_email
    if data.secondary_guest_name is not None:
        row.secondary_guest_name = (
            data.secondary_guest_name.strip() if data.secondary_guest_name else None
        )
    if data.secondary_guest_email is not None:
        row.secondary_guest_email = data.secondary_guest_email
    if data.city is not None:
        row.city = data.city
    if data.date_from is not None:
        row.date_from = data.date_from
    if data.date_to is not None:
        row.date_to = data.date_to
    if data.room_type is not None:
        row.room_type = data.room_type
    if final_rt == RoomType.SINGLE:
        row.bed_preference = None
    elif data.bed_preference is not None:
        row.bed_preference = data.bed_preference
    if data.note is not None:
        row.note = data.note

    _normalize_row_guest_fields(row)

    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation updated id=%s", row.id)

    guest_lines = (
        f"Pro koho: {_enum_str(row.reservation_for)} | Počet osob: {row.staying_person_count}\n"
        f"Hlavní ubytovaná: {row.primary_guest_name} <{row.primary_guest_email}>\n"
    )
    if row.staying_person_count == 2 and row.secondary_guest_name:
        guest_lines += (
            f"Druhá osoba: {row.secondary_guest_name} <{row.secondary_guest_email}>\n"
        )
    body = (
        f"Požadavek byl upraven.\n"
        f"ID: {row.id}\n"
        f"Žadatel: {row.requester_name} <{row.requester_email}>\n"
        f"{guest_lines}"
        f"Stav: {_enum_str(row.status)}\n"
    )
    _notify_reception_safe(f"[Hotel] Úprava požadavku {row.id}", body)
    return _reservation_read_from_row(row)


def cancel_reservation(session: Session, reservation_id: UUID, user: User) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    _ensure_employee_owns(row, user)
    if row.status == RequestStatus.CANCELLED:
        return _reservation_read_from_row(row)

    was_booked = row.status == RequestStatus.BOOKED
    row.status = RequestStatus.CANCELLED
    now = datetime.utcnow()
    row.cancelled_at = now
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation cancelled id=%s", row.id)

    text = (
        f"Požadavek byl zrušen žadatelem.\n"
        f"ID: {row.id}\n"
        f"Žadatel: {row.requester_name} <{row.requester_email}>\n"
        f"Hlavní ubytovaná: {row.primary_guest_name} <{row.primary_guest_email}>\n"
    )
    if was_booked:
        text += (
            f"(Dříve potvrzená rezervace — hotel: {row.hotel_name or '—'}, "
            f"č. {row.reservation_number or '—'})\n"
        )
    _notify_reception_safe(f"[Hotel] Zrušení požadavku {row.id}", text)
    return _reservation_read_from_row(row)


def list_admin_reservations(
    session: Session, status: Optional[RequestStatus] = None
) -> List[AdminReservationRead]:
    q = select(ReservationRequest).order_by(ReservationRequest.created_at.desc())
    if status is not None:
        q = q.where(col(ReservationRequest.status) == status)
    rows = session.exec(q).all()
    return [_admin_reservation_read_from_row(r) for r in rows]


def get_reservation_admin(session: Session, reservation_id: UUID) -> AdminReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _admin_reservation_read_from_row(row)


def update_reception_internal_note(
    session: Session, reservation_id: UUID, data: ReceptionInternalNoteBody
) -> AdminReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    row.reception_internal_note = data.reception_internal_note
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reception internal note updated id=%s", row.id)
    return _admin_reservation_read_from_row(row)


def update_status(
    session: Session, reservation_id: UUID, data: StatusUpdateBody
) -> AdminReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")

    previous_status = row.status

    if data.status == RequestStatus.BOOKED:
        if not data.hotel_name or not data.reservation_number:
            raise HTTPException(
                status_code=400,
                detail="hotel_name and reservation_number are required when status is BOOKED",
            )

    row.status = data.status
    if data.status == RequestStatus.BOOKED:
        row.was_ever_booked = True
    if data.hotel_name is not None:
        row.hotel_name = data.hotel_name
    if data.reservation_number is not None:
        row.reservation_number = data.reservation_number
    row.updated_at = datetime.utcnow()

    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation status updated id=%s status=%s", row.id, _enum_str(row.status))

    if data.status == RequestStatus.BOOKED and previous_status != RequestStatus.BOOKED:
        booked_body = (
            f"Ahoj {row.requester_name},\n\n"
            f"potvrzujeme tvoji rezervaci v hotelu {row.hotel_name}, č. {row.reservation_number}.\n\n"
            f"Hezký den."
        )
        _notify_employee_safe(
            row.requester_email,
            f"[Hotel] Rezervace potvrzena {row.reservation_number}",
            booked_body,
        )

    return _admin_reservation_read_from_row(row)
