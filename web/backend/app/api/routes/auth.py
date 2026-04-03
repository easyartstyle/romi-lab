from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.schemas.auth import AuthResponse, InviteAcceptRequest, InviteInfoResponse, LoginRequest, RegisterRequest
from app.schemas.user import UserRead
from app.services.auth_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    accept_invite,
    authenticate_user,
    get_user_by_invite_token,
    issue_access_token,
    register_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = register_user(db, payload.email, payload.password, payload.full_name)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    token, issued_at = issue_access_token(user)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        access_token=token,
        issued_at=issued_at,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    token, issued_at = issue_access_token(user)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        access_token=token,
        issued_at=issued_at,
    )


@router.get("/me", response_model=UserRead)
def me(current_user=Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/invite/{token}", response_model=InviteInfoResponse)
def get_invite_info(token: str, db: Session = Depends(get_db)) -> InviteInfoResponse:
    user = get_user_by_invite_token(db, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite link is invalid or expired")

    return InviteInfoResponse(email=user.email, full_name=user.full_name, role=user.role)


@router.post("/invite/accept", response_model=AuthResponse)
def accept_invite_route(payload: InviteAcceptRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = accept_invite(db, payload.token, payload.password)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token, issued_at = issue_access_token(user)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        access_token=token,
        issued_at=issued_at,
    )