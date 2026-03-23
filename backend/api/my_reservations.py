from typing import List

from fastapi import APIRouter

from api.dependencies import EmployeeUser, SessionDep
from application import reservation_service as reservation_service
from schemas.reservation import ReservationRead

router = APIRouter()


@router.get("/reservations", response_model=List[ReservationRead])
def list_my_reservations(session: SessionDep, user: EmployeeUser) -> List[ReservationRead]:
    return reservation_service.list_my_reservations(session, user)
