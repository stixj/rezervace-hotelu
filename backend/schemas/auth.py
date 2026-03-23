from datetime import datetime
from uuid import UUID

import email_validator as ev
from pydantic import BaseModel, Field, field_validator

from infrastructure.models import UserRole


class LoginRequest(BaseModel):
    """Login email uses test_environment=True so dev addresses like @local.test validate."""

    email: str
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        raw = v.strip().lower()
        try:
            return ev.validate_email(
                raw, check_deliverability=False, test_environment=True
            ).normalized
        except ev.EmailNotValidError as e:
            raise ValueError(str(e)) from e


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    created_at: datetime
