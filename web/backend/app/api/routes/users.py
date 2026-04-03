from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.user import UserInviteRequest, UserInviteResponse, UserRead, UserUpdateRequest
from app.services.auth_service import UserAlreadyExistsError, issue_invite_token, register_user
from app.services.project_service import ProjectAccessDeniedError, ProjectNotFoundError, assign_user_to_project


router = APIRouter(prefix="/users", tags=["users"])


def _ensure_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@router.get("", response_model=list[UserRead])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    _ensure_admin(current_user)
    users = db.scalars(select(User).order_by(User.created_at.asc(), User.id.asc())).all()
    return [UserRead.model_validate(user) for user in users]


@router.post("/invite", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: UserInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserInviteResponse:
    _ensure_admin(current_user)
    try:
        user = register_user(
            db,
            payload.email,
            "invite-pending-password",
            payload.full_name,
            payload.role.strip().lower(),
            is_active=False,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists") from exc

    if payload.project_id is not None:
        try:
            assign_user_to_project(db, current_user, payload.project_id, user.email, (payload.project_role or "client").strip().lower())
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found") from exc
        except ProjectAccessDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    invite_token = issue_invite_token(user)
    invite_url = f"{settings.frontend_base_url}/invite/{invite_token}"
    return UserInviteResponse(
        user=UserRead.model_validate(user),
        invite_url=invite_url,
        project_id=payload.project_id,
        project_role=(payload.project_role or "client").strip().lower() if payload.project_id is not None else None,
    )


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    _ensure_admin(current_user)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = payload.role.strip().lower()
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _ensure_admin(current_user)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")
    if user.email.lower().strip() == settings.primary_owner_email.lower().strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary owner account cannot be deleted")

    primary_owner = db.scalar(select(User).where(User.email == settings.primary_owner_email.lower().strip()))
    if primary_owner is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary owner account not found")

    owned_projects = db.scalars(select(Project).where(Project.owner_user_id == user.id)).all()
    for project in owned_projects:
        project.owner_user_id = primary_owner.id
        primary_membership = db.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == primary_owner.id)
        )
        if primary_membership is None:
            db.add(ProjectMember(project_id=project.id, user_id=primary_owner.id, role="owner"))
        else:
            primary_membership.role = "owner"

    memberships = db.scalars(select(ProjectMember).where(ProjectMember.user_id == user.id)).all()
    for membership in memberships:
        db.delete(membership)

    db.delete(user)
    db.commit()
