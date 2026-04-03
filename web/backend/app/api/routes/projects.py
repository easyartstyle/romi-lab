from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.connection import ProjectConnectionRead, ProjectConnectionTestResult, ProjectConnectionUpsertRequest
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDashboardRead,
    ProjectDataImportRequest,
    ProjectDataImportResult,
    ProjectMemberAssignRequest,
    ProjectMemberRead,
    ProjectMemberUpdateRequest,
    ProjectPlanRead,
    ProjectPlanUpsertRequest,
    ProjectRead,
)
from app.services.project_service import (
    ProjectAccessDeniedError,
    ProjectMemberAlreadyExistsError,
    ProjectMemberNotFoundError,
    ProjectNotFoundError,
    ProjectServiceError,
    UserNotFoundError,
    assign_user_to_project,
    build_project_dashboard_summary,
    create_project,
    delete_project,
    delete_project_connection,
    delete_project_plan,
    get_project_for_user,
    import_project_data,
    list_project_connections,
    list_project_members,
    list_project_plans,
    remove_project_member,
    test_project_connection,
    update_project_member_role,
    upsert_project_connection,
    upsert_project_plan,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _member_to_read(membership: ProjectMember) -> ProjectMemberRead:
    return ProjectMemberRead(
        id=membership.id,
        project_id=membership.project_id,
        user_id=membership.user_id,
        role=membership.role,
        is_owner=membership.project.owner_user_id == membership.user_id if membership.project else False,
        created_at=membership.created_at,
        email=membership.user.email if membership.user else None,
        full_name=membership.user.full_name if membership.user else None,
        system_role=membership.user.role if membership.user else None,
    )


@router.get("/my", response_model=list[ProjectRead])
def list_my_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    if current_user.role == "admin":
        projects = db.scalars(select(Project).order_by(Project.updated_at.desc(), Project.id.desc())).all()
        return [ProjectRead.model_validate(project) for project in projects]

    stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == current_user.id)
        .order_by(Project.updated_at.desc(), Project.id.desc())
    )
    projects = db.scalars(stmt).all()
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    try:
        project = get_project_for_user(db, current_user, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return ProjectRead.model_validate(project)


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardRead)
def get_project_dashboard(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectDashboardRead:
    try:
        project = get_project_for_user(db, current_user, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return build_project_dashboard_summary(db, project)


@router.get("/{project_id}/plans", response_model=list[ProjectPlanRead])
def get_project_plans(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectPlanRead]:
    try:
        return list_project_plans(db, current_user, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/{project_id}/plans", response_model=ProjectPlanRead, status_code=status.HTTP_201_CREATED)
def save_project_plan(
    project_id: int,
    payload: ProjectPlanUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPlanRead:
    try:
        return upsert_project_plan(db, current_user, project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{project_id}/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_plan(
    project_id: int,
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_project_plan(db, current_user, project_id, plan_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/{project_id}/data/import", response_model=ProjectDataImportResult)
def import_data_into_project(
    project_id: int,
    payload: ProjectDataImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectDataImportResult:
    try:
        return import_project_data(db, current_user, project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_new_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectRead:
    if current_user.role == "client":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client cannot create projects")
    project = create_project(db, current_user, payload.name, payload.slug)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_project(db, current_user, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: int,
    payload: ProjectMemberAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMemberRead:
    try:
        membership = assign_user_to_project(db, current_user, project_id, payload.email, payload.role)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectMemberAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return _member_to_read(membership)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def get_project_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectMemberRead]:
    try:
        memberships = list_project_members(db, current_user, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return [_member_to_read(membership) for membership in memberships]


@router.patch("/{project_id}/members/{member_id}", response_model=ProjectMemberRead)
def edit_project_member(
    project_id: int,
    member_id: int,
    payload: ProjectMemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMemberRead:
    try:
        membership = update_project_member_role(db, current_user, project_id, member_id, payload.role)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectMemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _member_to_read(membership)


@router.delete("/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def drop_project_member(
    project_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        remove_project_member(db, current_user, project_id, member_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectMemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{project_id}/connections", response_model=list[ProjectConnectionRead])
def get_project_connections(
    project_id: int,
    category: str = "ads",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectConnectionRead]:
    try:
        return list_project_connections(db, current_user, project_id, category)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/{project_id}/connections", response_model=ProjectConnectionRead, status_code=status.HTTP_201_CREATED)
def save_project_connection(
    project_id: int,
    payload: ProjectConnectionUpsertRequest,
    connection_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectConnectionRead:
    try:
        return upsert_project_connection(db, current_user, project_id, payload, connection_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{project_id}/connections/{connection_id}/test", response_model=ProjectConnectionTestResult)
def run_project_connection_test(
    project_id: int,
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectConnectionTestResult:
    try:
        return test_project_connection(db, current_user, project_id, connection_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ProjectServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{project_id}/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_connection(
    project_id: int,
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_project_connection(db, current_user, project_id, connection_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
