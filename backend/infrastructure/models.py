import enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy.types import String
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
    city: str = Field(sa_column=Column(String))
    date_from: date
    date_to: date
    room_type: RoomType = Field(sa_column=Column(String))
    bed_preference: Optional[BedPreference] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    note: Optional[str] = None
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
