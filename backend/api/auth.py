from fastapi import APIRouter

from api.dependencies import AnyAuthUser, SessionDep
from application import auth_service
from schemas.auth import LoginRequest, TokenResponse, UserMeResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(session: SessionDep, body: LoginRequest) -> TokenResponse:
    user = auth_service.authenticate(session, str(body.email), body.password)
    token = auth_service.create_access_token(
        user_id=user.id, email=user.email, role=user.role
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserMeResponse)
def me(user: AnyAuthUser) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )
