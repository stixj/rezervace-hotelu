from datetime import date, datetime
from typing import Optional
from uuid import UUID

import email_validator as ev
from pydantic import BaseModel, Field, field_validator, model_validator

from infrastructure.models import (
    BedPreference,
    RequestStatus,
    RequestUrgency,
    ReservationFor,
    RoomType,
)

# Shown by GET /__hotel_ready — if your browser still gets enum errors for city, this PID/server is stale.
RESERVATION_CITY_BODY_SCHEMA = "free_text_string"


def _guest_email_normalized(raw: str) -> str:
    try:
        return ev.validate_email(
            raw.strip().lower(), check_deliverability=False, test_environment=True
        ).normalized
    except ev.EmailNotValidError as e:
        raise ValueError(str(e)) from e


class ReservationCreate(BaseModel):
    """Create payload for authenticated employee; requester email comes from the logged-in user."""

    requester_name: str = Field(..., min_length=1)
    reservation_for: ReservationFor = ReservationFor.SELF
    staying_person_count: int = Field(default=1, ge=1, le=2)
    primary_guest_name: Optional[str] = None
    primary_guest_email: Optional[str] = None
    secondary_guest_name: Optional[str] = None
    secondary_guest_email: Optional[str] = None
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
    def validate_guest_fields(self):
        if self.reservation_for == ReservationFor.COLLEAGUE:
            pn = (self.primary_guest_name or "").strip()
            pe = (self.primary_guest_email or "").strip()
            if not pn:
                raise ValueError("primary_guest_name is required when reservation_for is COLLEAGUE")
            if not pe:
                raise ValueError("primary_guest_email is required when reservation_for is COLLEAGUE")
            self.primary_guest_name = pn
            try:
                self.primary_guest_email = _guest_email_normalized(pe)
            except ValueError as e:
                raise ValueError(f"primary_guest_email: {e}") from e
        else:
            self.primary_guest_name = None
            self.primary_guest_email = None

        if self.staying_person_count == 2:
            sn = (self.secondary_guest_name or "").strip()
            se = (self.secondary_guest_email or "").strip()
            if not sn:
                raise ValueError(
                    "secondary_guest_name is required when staying_person_count is 2"
                )
            if not se:
                raise ValueError(
                    "secondary_guest_email is required when staying_person_count is 2"
                )
            self.secondary_guest_name = sn
            try:
                self.secondary_guest_email = _guest_email_normalized(se)
            except ValueError as e:
                raise ValueError(f"secondary_guest_email: {e}") from e
        else:
            self.secondary_guest_name = None
            self.secondary_guest_email = None
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
    reservation_for: Optional[ReservationFor] = None
    staying_person_count: Optional[int] = Field(None, ge=1, le=2)
    primary_guest_name: Optional[str] = None
    primary_guest_email: Optional[str] = None
    secondary_guest_name: Optional[str] = None
    secondary_guest_email: Optional[str] = None
    city: Optional[str] = Field(None, min_length=1, max_length=200)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    room_type: Optional[RoomType] = None
    bed_preference: Optional[BedPreference] = None
    note: Optional[str] = None
    urgency: Optional[RequestUrgency] = None
    urgency_reason: Optional[str] = Field(None, max_length=500)

    @field_validator("urgency_reason")
    @classmethod
    def urgency_reason_stripped_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None

    @model_validator(mode="after")
    def validate_urgency_reason_update(self):
        u = self.urgency
        if u is None:
            return self
        if u == RequestUrgency.URGENT:
            if not self.urgency_reason:
                raise ValueError("urgency_reason is required when urgency is URGENT")
        elif u == RequestUrgency.STANDARD:
            self.urgency_reason = None
        return self

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

    @field_validator("primary_guest_email", "secondary_guest_email")
    @classmethod
    def optional_guest_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        try:
            return _guest_email_normalized(s)
        except ValueError as e:
            raise ValueError(str(e)) from e


class StatusUpdateBody(BaseModel):
    status: RequestStatus
    hotel_name: Optional[str] = None
    reservation_number: Optional[str] = None


class ChangeRequestFieldRead(BaseModel):
    """Single field diff for reception / employee (human-readable values)."""

    field_key: str
    label: str
    old_value: str
    new_value: str


class PendingChangeRead(BaseModel):
    submitted_at: datetime
    reservation_status_at_submit: RequestStatus
    changes: list[ChangeRequestFieldRead]


class ReceptionInternalNoteBody(BaseModel):
    """Reception-only; stored separately from employee `note`."""

    reception_internal_note: Optional[str] = Field(None, max_length=20000)

    @field_validator("reception_internal_note")
    @classmethod
    def strip_internal_note(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class ReservationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    user_id: Optional[UUID] = None
    requester_name: str
    requester_email: str
    reservation_for: ReservationFor
    staying_person_count: int
    primary_guest_name: str
    primary_guest_email: str
    secondary_guest_name: Optional[str]
    secondary_guest_email: Optional[str]
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
    pending_change: Optional[PendingChangeRead] = None


class AdminReservationRead(ReservationRead):
    """Admin/reception API only — includes fields hidden from employee clients."""

    reception_internal_note: Optional[str] = None
