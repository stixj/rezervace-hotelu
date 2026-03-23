from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query

from api.dependencies import ReceptionUser, SessionDep
from application import reservation_service as reservation_service
from infrastructure.models import RequestStatus
from schemas.reservation import ReservationRead, StatusUpdateBody

router = APIRouter()


@router.get("", response_model=List[ReservationRead])
def list_reservations(
    session: SessionDep,
    _: ReceptionUser,
    status: Optional[RequestStatus] = Query(None),
) -> List[ReservationRead]:
    return reservation_service.list_admin_reservations(session, status)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    session: SessionDep, _: ReceptionUser, reservation_id: UUID
) -> ReservationRead:
    return reservation_service.get_reservation_admin(session, reservation_id)


@router.post("/{reservation_id}/status", response_model=ReservationRead)
def update_status(
    session: SessionDep,
    _: ReceptionUser,
    reservation_id: UUID,
    body: StatusUpdateBody,
) -> ReservationRead:
    return reservation_service.update_status(session, reservation_id, body)
