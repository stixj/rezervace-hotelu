import enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.types import String, Text
from sqlmodel import Field, SQLModel


class UserRole(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    RECEPTION = "RECEPTION"


class RequestStatus(str, enum.Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"


class RequestUrgency(str, enum.Enum):
    STANDARD = "STANDARD"
    URGENT = "URGENT"


class RoomType(str, enum.Enum):
    SINGLE = "single"
    MULTI = "multi"


class BedPreference(str, enum.Enum):
    DOUBLE = "double"
    TWIN = "twin"


class ReservationFor(str, enum.Enum):
    """Who the stay is booked for (submitter may differ)."""

    SELF = "SELF"
    COLLEAGUE = "COLLEAGUE"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: UserRole = Field(sa_column=Column(String))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReservationRequest(SQLModel, table=True):
    __tablename__ = "reservation_request"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    requester_name: str
    requester_email: str
    reservation_for: ReservationFor = Field(
        default=ReservationFor.SELF, sa_column=Column(String)
    )
    staying_person_count: int = Field(default=1)
    primary_guest_name: str
    primary_guest_email: str
    secondary_guest_name: Optional[str] = None
    secondary_guest_email: Optional[str] = None
    city: str = Field(sa_column=Column(String))
    date_from: date
    date_to: date
    room_type: RoomType = Field(sa_column=Column(String))
    bed_preference: Optional[BedPreference] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    note: Optional[str] = None
    reception_internal_note: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    urgency: RequestUrgency = Field(
        default=RequestUrgency.STANDARD, sa_column=Column(String)
    )
    urgency_reason: Optional[str] = Field(
        default=None, sa_column=Column(String(500), nullable=True)
    )
    was_ever_booked: bool = Field(default=False)
    status: RequestStatus = Field(
        default=RequestStatus.NEW, sa_column=Column(String)
    )
    hotel_name: Optional[str] = None
    reservation_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    pending_change_submitted_at: Optional[datetime] = None
    pending_change_json: Optional[str] = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # Reception work history (last occurrence only; not a full audit trail)
    last_change_request_at: Optional[datetime] = None
    last_change_cleared_at: Optional[datetime] = None
