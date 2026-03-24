from uuid import UUID

from fastapi import APIRouter

from api.dependencies import EmployeeUser, SessionDep
from application import reservation_service as reservation_service
from schemas.reservation import (
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
)

router = APIRouter()


@router.post("", response_model=ReservationRead)
def create_reservation(
    session: SessionDep, user: EmployeeUser, body: ReservationCreate
) -> ReservationRead:
    return reservation_service.create_reservation(session, body, user)


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    session: SessionDep, user: EmployeeUser, reservation_id: UUID
) -> ReservationRead:
    return reservation_service.get_reservation_for_employee(session, reservation_id, user)


@router.put("/{reservation_id}", response_model=ReservationRead)
def update_reservation(
    session: SessionDep,
    user: EmployeeUser,
    reservation_id: UUID,
    body: ReservationUpdate,
) -> ReservationRead:
    return reservation_service.update_reservation(session, reservation_id, body, user)


@router.post("/{reservation_id}/change-request", response_model=ReservationRead)
def submit_change_request(
    session: SessionDep,
    user: EmployeeUser,
    reservation_id: UUID,
    body: ReservationCreate,
) -> ReservationRead:
    return reservation_service.submit_change_request(session, reservation_id, body, user)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(
    session: SessionDep, user: EmployeeUser, reservation_id: UUID
) -> ReservationRead:
    return reservation_service.cancel_reservation(session, reservation_id, user)
