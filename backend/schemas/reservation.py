from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from infrastructure.models import BedPreference, RequestStatus, RequestUrgency, RoomType

# Shown by GET /__hotel_ready — if your browser still gets enum errors for city, this PID/server is stale.
RESERVATION_CITY_BODY_SCHEMA = "free_text_string"

class ReservationCreate(BaseModel):
    """Create payload for authenticated employee; email comes from the logged-in user."""

    requester_name: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1, max_length=200)
    date_from: date
    date_to: date
    room_type: RoomType
    bed_preference: Optional[BedPreference] = None
    note: Optional[str] = None
    urgency: RequestUrgency = RequestUrgency.STANDARD
    urgency_reason: Optional[str] = Field(None, max_length=500)

    @field_validator("city")
    @classmethod
    def city_stripped(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("city cannot be empty")
        return s

    @field_validator("urgency_reason")
    @classmethod
    def urgency_reason_stripped(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @model_validator(mode="after")
    def validate_bed_preference(self):
        if self.room_type == RoomType.SINGLE and self.bed_preference is not None:
            raise ValueError("bed_preference must be None when room_type is single")
        return self

    @model_validator(mode="after")
    def validate_urgency_reason(self):
        if self.urgency == RequestUrgency.URGENT:
            if not self.urgency_reason:
                raise ValueError("urgency_reason is required when urgency is URGENT")
        else:
            self.urgency_reason = None
        return self


class ReservationUpdate(BaseModel):
    """Employee update; ownership enforced in the service from the current user."""

    requester_name: Optional[str] = Field(None, min_length=1)
    city: Optional[str] = Field(None, min_length=1, max_length=200)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    room_type: Optional[RoomType] = None
    bed_preference: Optional[BedPreference] = None
    note: Optional[str] = None

    @field_validator("city")
    @classmethod
    def city_stripped_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("city cannot be empty")
        return s

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
    city: str
    date_from: date
    date_to: date
    room_type: RoomType
    bed_preference: Optional[BedPreference]
    note: Optional[str]
    urgency: RequestUrgency
    urgency_reason: Optional[str]
    was_ever_booked: bool
    status: RequestStatus
    hotel_name: Optional[str]
    reservation_number: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    cancelled_at: Optional[datetime]
