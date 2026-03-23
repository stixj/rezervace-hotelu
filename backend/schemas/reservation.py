from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from infrastructure.models import BedPreference, City, RequestStatus, RoomType


class ReservationCreate(BaseModel):
    """Create payload for authenticated employee; email comes from the logged-in user."""

    requester_name: str = Field(..., min_length=1)
    city: City
    date_from: date
    date_to: date
    room_type: RoomType
    bed_preference: Optional[BedPreference] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_bed_preference(self):
        if self.room_type == RoomType.SINGLE and self.bed_preference is not None:
            raise ValueError("bed_preference must be None when room_type is single")
        return self


class ReservationUpdate(BaseModel):
    """Employee update; ownership enforced in the service from the current user."""

    requester_name: Optional[str] = Field(None, min_length=1)
    city: Optional[City] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    room_type: Optional[RoomType] = None
    bed_preference: Optional[BedPreference] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_bed_preference(self):
        rt = self.room_type
        if rt is None:
            return self
        if rt == RoomType.SINGLE and self.bed_preference is not None:
            raise ValueError("bed_preference must be None when room_type is single")
        return self


class StatusUpdateBody(BaseModel):
    status: RequestStatus
    hotel_name: Optional[str] = None
    reservation_number: Optional[str] = None


class ReservationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    user_id: Optional[UUID] = None
    requester_name: str
    requester_email: str
    city: City
    date_from: date
    date_to: date
    room_type: RoomType
    bed_preference: Optional[BedPreference]
    note: Optional[str]
    status: RequestStatus
    hotel_name: Optional[str]
    reservation_number: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    cancelled_at: Optional[datetime]
