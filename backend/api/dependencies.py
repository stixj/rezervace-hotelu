from typing import Annotated, Callable, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from application import auth_service
from infrastructure.database import get_session
from infrastructure.models import User, UserRole

SessionDep = Annotated[Session, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def get_token_credentials(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> str:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return creds.credentials


def get_current_user(
    session: SessionDep, token: Annotated[str, Depends(get_token_credentials)]
) -> User:
    payload = auth_service.decode_token(token)
    return auth_service.user_from_token_payload(session, payload)


def _coerce_role(role: UserRole | str) -> UserRole:
    if isinstance(role, UserRole):
        return role
    return UserRole(role)


def require_roles(*allowed: UserRole) -> Callable[..., User]:
    allowed_set = frozenset(allowed)

    def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if _coerce_role(user.role) not in allowed_set:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dep


EmployeeUser = Annotated[User, Depends(require_roles(UserRole.EMPLOYEE))]
ReceptionUser = Annotated[User, Depends(require_roles(UserRole.RECEPTION))]
AnyAuthUser = Annotated[User, Depends(get_current_user)]
