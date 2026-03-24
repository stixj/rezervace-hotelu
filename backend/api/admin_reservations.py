from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.dependencies import ReceptionUser, SessionDep
from application import reservation_service as reservation_service
from infrastructure.models import RequestStatus
from schemas.reservation import (
    AdminReservationRead,
    ReceptionInternalNoteBody,
    StatusUpdateBody,
)

router = APIRouter()


@router.get("", response_model=List[AdminReservationRead])
def list_reservations(
    session: SessionDep,
    _: ReceptionUser,
    status: Optional[RequestStatus] = Query(None),
) -> List[AdminReservationRead]:
    return reservation_service.list_admin_reservations(session, status)


@router.get("/{reservation_id}", response_model=AdminReservationRead)
def get_reservation(
    session: SessionDep, _: ReceptionUser, reservation_id: UUID
) -> AdminReservationRead:
    return reservation_service.get_reservation_admin(session, reservation_id)


@router.post("/{reservation_id}/status", response_model=AdminReservationRead)
def update_status(
    session: SessionDep,
    _: ReceptionUser,
    reservation_id: UUID,
    body: StatusUpdateBody,
) -> AdminReservationRead:
    return reservation_service.update_status(session, reservation_id, body)


@router.put("/{reservation_id}/reception-internal-note", response_model=AdminReservationRead)
def put_reception_internal_note(
    session: SessionDep,
    _: ReceptionUser,
    reservation_id: UUID,
    body: ReceptionInternalNoteBody,
) -> AdminReservationRead:
    return reservation_service.update_reception_internal_note(session, reservation_id, body)


@router.post(
    "/{reservation_id}/pending-change/clear",
    response_model=AdminReservationRead,
)
def clear_pending_change(
    session: SessionDep,
    _: ReceptionUser,
    reservation_id: UUID,
) -> AdminReservationRead:
    return reservation_service.clear_pending_change_request(session, reservation_id)
