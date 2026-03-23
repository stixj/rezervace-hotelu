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
    ReservationRequest,
    RoomType,
    User,
)
from schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate, StatusUpdateBody

logger = logging.getLogger(__name__)


def _enum_str(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


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
    row = ReservationRequest(
        user_id=user.id,
        requester_name=data.requester_name,
        requester_email=_normalize_email(user.email),
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
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation created id=%s user_id=%s", row.id, row.user_id)

    body = (
        f"Nový požadavek na rezervaci.\n"
        f"ID: {row.id}\n"
        f"Žadatel: {row.requester_name} <{row.requester_email}>\n"
        f"Město: {_enum_str(row.city)}\n"
        f"Termín: {row.date_from} – {row.date_to}\n"
        f"Typ pokoje: {_enum_str(row.room_type)}\n"
    )
    if row.urgency == RequestUrgency.URGENT:
        body += f"Urgence: urgentní\nDůvod: {row.urgency_reason}\n"
    _notify_reception_safe(f"[Hotel] Nový požadavek {row.id}", body)
    return ReservationRead.model_validate(row)


def list_my_reservations(session: Session, user: User) -> List[ReservationRead]:
    rows = session.exec(
        select(ReservationRequest)
        .where(col(ReservationRequest.user_id) == user.id)
        .order_by(ReservationRequest.created_at.desc())
    ).all()
    return [ReservationRead.model_validate(r) for r in rows]


def get_reservation_for_employee(session: Session, reservation_id: UUID, user: User) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    _ensure_employee_owns(row, user)
    return ReservationRead.model_validate(row)


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

    final_rt = data.room_type if data.room_type is not None else row.room_type
    if final_rt == RoomType.SINGLE:
        final_bed = None
    else:
        final_bed = (
            data.bed_preference if data.bed_preference is not None else row.bed_preference
        )
    _apply_bed_preference_rules(final_rt, final_bed)

    if data.requester_name is not None:
        row.requester_name = data.requester_name
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

    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info("Reservation updated id=%s", row.id)

    body = (
        f"Požadavek byl upraven.\n"
        f"ID: {row.id}\n"
        f"Žadatel: {row.requester_name} <{row.requester_email}>\n"
        f"Stav: {_enum_str(row.status)}\n"
    )
    _notify_reception_safe(f"[Hotel] Úprava požadavku {row.id}", body)
    return ReservationRead.model_validate(row)


def cancel_reservation(session: Session, reservation_id: UUID, user: User) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    _ensure_employee_owns(row, user)
    if row.status == RequestStatus.CANCELLED:
        return ReservationRead.model_validate(row)

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
    )
    if was_booked:
        text += (
            f"(Dříve potvrzená rezervace — hotel: {row.hotel_name or '—'}, "
            f"č. {row.reservation_number or '—'})\n"
        )
    _notify_reception_safe(f"[Hotel] Zrušení požadavku {row.id}", text)
    return ReservationRead.model_validate(row)


def list_admin_reservations(
    session: Session, status: Optional[RequestStatus] = None
) -> List[ReservationRead]:
    q = select(ReservationRequest).order_by(ReservationRequest.created_at.desc())
    if status is not None:
        q = q.where(col(ReservationRequest.status) == status)
    rows = session.exec(q).all()
    return [ReservationRead.model_validate(r) for r in rows]


def get_reservation_admin(session: Session, reservation_id: UUID) -> ReservationRead:
    row = session.get(ReservationRequest, reservation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return ReservationRead.model_validate(row)


def update_status(
    session: Session, reservation_id: UUID, data: StatusUpdateBody
) -> ReservationRead:
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

    return ReservationRead.model_validate(row)
