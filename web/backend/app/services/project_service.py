import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import re
from datetime import datetime

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ads_raw_data import AdsRawData
from app.models.crm_raw_data import CrmRawData
from app.models.project import Project
from app.models.project_connection import ProjectConnection
from app.models.project_member import ProjectMember
from app.models.project_plan import ProjectPlan
from app.models.user import User
from app.schemas.connection import ProjectConnectionRead, ProjectConnectionTestResult, ProjectConnectionUpsertRequest
from app.schemas.project import (
    AdsImportRow,
    CrmImportRow,
    DashboardFilterOptionRead,
    DashboardMetricRead,
    DashboardRecordRead,
    DashboardTableRowRead,
    ProjectDashboardRead,
    ProjectDataImportRequest,
    ProjectDataImportResult,
    ProjectPlanRead,
    ProjectPlanUpsertRequest,
    ProjectRead,
)
from web.shared.analytics_core import build_merged_dataframe_from_sources
from web.shared.kpi_core import calculate_kpi_metrics, format_kpi_values


class ProjectServiceError(Exception):
    pass


class ProjectAccessDeniedError(ProjectServiceError):
    pass


class ProjectNotFoundError(ProjectServiceError):
    pass


class ProjectMemberAlreadyExistsError(ProjectServiceError):
    pass


class ProjectMemberNotFoundError(ProjectServiceError):
    pass


class UserNotFoundError(ProjectServiceError):
    pass

def _is_primary_owner_user(user: User | None) -> bool:
    return bool(user and user.email and user.email.lower().strip() == settings.primary_owner_email.lower().strip())


def _get_primary_owner_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == settings.primary_owner_email.lower().strip()))
    if user is None:
        raise ProjectServiceError("Primary owner account not found")
    return user


def _get_or_create_project_membership(db: Session, project_id: int, user_id: int, role: str) -> ProjectMember:
    membership = db.scalar(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    if membership is None:
        membership = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        db.add(membership)
        db.flush()
    else:
        membership.role = role
    return membership


def _set_project_owner(db: Session, project: Project, new_owner: User, fallback_previous_role: str = "editor") -> None:
    previous_owner_id = project.owner_user_id
    if previous_owner_id and previous_owner_id != new_owner.id:
        previous_membership = db.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project.id, ProjectMember.user_id == previous_owner_id)
        )
        if previous_membership is not None:
            previous_membership.role = fallback_previous_role
    project.owner_user_id = new_owner.id
    _get_or_create_project_membership(db, project.id, new_owner.id, "owner")


COL_DATE = "Дата"
COL_SOURCE = "Источник"
COL_TYPE = "Тип"
COL_CAMPAIGN = "Кампания"
COL_GROUP = "Группа"
COL_AD = "Объявление"
COL_KEYWORD = "Ключевая фраза"
COL_REGION = "Регион"
COL_DEVICE = "Устройство"
COL_PLACEMENT = "Площадка"
COL_POSITION = "Position"
COL_URL = "URL"
COL_PRODUCT = "Продукт"
COL_COST = "Расход"
COL_IMPRESSIONS = "Показы"
COL_CLICKS = "Клики"
COL_LEADS = "Лиды"
COL_SALES = "Продажи"
COL_REVENUE = "Выручка"
COL_MARGIN = "Маржа"
COL_AVG_CHECK = "Ср.чек"
COL_MEDIUM = "Medium"


CONNECTION_PLATFORM_LABELS = {
    "yandex_direct": "Яндекс.Директ",
    "google_ads": "Google Ads",
    "vk_ads": "VK Ads",
    "telegram_ads": "Telegram Ads",
}


def _normalize_connection_platform(value: str) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned or "yandex_direct"


def _connection_platform_label(platform: str) -> str:
    return CONNECTION_PLATFORM_LABELS.get(platform, platform)


def list_project_connections(db: Session, current_user: User, project_id: int, category: str = "ads") -> list[ProjectConnectionRead]:
    get_project_for_user(db, current_user, project_id)
    connections = db.scalars(
        select(ProjectConnection)
        .where(ProjectConnection.project_id == project_id, ProjectConnection.category == category)
        .order_by(ProjectConnection.updated_at.desc(), ProjectConnection.id.desc())
    ).all()
    return [ProjectConnectionRead.model_validate(connection) for connection in connections]


def upsert_project_connection(
    db: Session,
    current_user: User,
    project_id: int,
    payload: ProjectConnectionUpsertRequest,
    connection_id: int | None = None,
) -> ProjectConnectionRead:
    get_project_for_user(db, current_user, project_id)

    platform = _normalize_connection_platform(payload.platform)
    identifier = payload.identifier.strip()
    client_login_mode = (payload.client_login_mode or "auto").strip() or "auto"

    if platform == "yandex_direct" and client_login_mode == "always" and not identifier:
        raise ProjectServiceError("Для режима 'Всегда использовать' заполните поле ID / логин.")

    connection: ProjectConnection | None = None
    if connection_id is not None:
        connection = db.scalar(select(ProjectConnection).where(ProjectConnection.id == connection_id, ProjectConnection.project_id == project_id))
        if connection is None:
            raise ProjectNotFoundError("Подключение не найдено")

    if connection is None:
        connection = ProjectConnection(project_id=project_id)
        db.add(connection)

    connection.category = (payload.category or "ads").strip() or "ads"
    connection.platform = platform
    connection.name = payload.name.strip()
    connection.identifier = identifier
    connection.api_mode = (payload.api_mode or "production").strip() or "production"
    connection.client_login_mode = client_login_mode
    connection.token = payload.token or ""
    connection.client_id = payload.client_id.strip()
    connection.client_secret = payload.client_secret.strip()
    connection.refresh_token = payload.refresh_token or ""
    connection.status = connection.status or "not_connected"
    connection.status_comment = connection.status_comment or "Подключение еще не проверено"

    db.commit()
    db.refresh(connection)
    return ProjectConnectionRead.model_validate(connection)


def test_project_connection(
    db: Session,
    current_user: User,
    project_id: int,
    connection_id: int,
) -> ProjectConnectionTestResult:
    get_project_for_user(db, current_user, project_id)
    connection = db.scalar(select(ProjectConnection).where(ProjectConnection.id == connection_id, ProjectConnection.project_id == project_id))
    if connection is None:
        raise ProjectNotFoundError("Подключение не найдено")

    now = datetime.utcnow()
    platform_label = _connection_platform_label(connection.platform)

    if connection.platform == "yandex_direct" and connection.client_login_mode == "always" and not connection.identifier.strip():
        connection.status = "error"
        connection.status_comment = "Для режима 'Всегда использовать' заполните поле ID / логин."
        connection.checked_at = now
        db.commit()
        db.refresh(connection)
        return ProjectConnectionTestResult(ok=False, status=connection.status, status_comment=connection.status_comment, checked_at=connection.checked_at)

    if connection.platform in {"yandex_direct", "vk_ads", "telegram_ads"} and not connection.token.strip():
        connection.status = "error"
        connection.status_comment = f"Для {platform_label} заполните поле Токен."
        connection.checked_at = now
        db.commit()
        db.refresh(connection)
        return ProjectConnectionTestResult(ok=False, status=connection.status, status_comment=connection.status_comment, checked_at=connection.checked_at)

    if connection.platform == "google_ads" and (not connection.client_id.strip() or not connection.client_secret.strip()):
        connection.status = "error"
        connection.status_comment = "Для Google Ads заполните Client ID и Client Secret."
        connection.checked_at = now
        db.commit()
        db.refresh(connection)
        return ProjectConnectionTestResult(ok=False, status=connection.status, status_comment=connection.status_comment, checked_at=connection.checked_at)

    connection.status = "connected"
    if connection.platform == "yandex_direct":
        if connection.client_login_mode == "always" and connection.identifier.strip():
            connection.status_comment = f"Локальная проверка пройдена. Используется Client-Login: {connection.identifier.strip()}"
        elif connection.identifier.strip():
            connection.status_comment = f"Локальная проверка пройдена. Кабинет: {connection.identifier.strip()}"
        else:
            connection.status_comment = "Локальная проверка пройдена. Используются данные владельца токена."
    else:
        connection.status_comment = f"Локальная проверка пройдена для {platform_label}."
    connection.checked_at = now
    db.commit()
    db.refresh(connection)
    return ProjectConnectionTestResult(ok=True, status=connection.status, status_comment=connection.status_comment, checked_at=connection.checked_at)


def delete_project_connection(db: Session, current_user: User, project_id: int, connection_id: int) -> None:
    get_project_for_user(db, current_user, project_id)
    connection = db.scalar(select(ProjectConnection).where(ProjectConnection.id == connection_id, ProjectConnection.project_id == project_id))
    if connection is None:
        raise ProjectNotFoundError("Подключение не найдено")
    db.delete(connection)
    db.commit()
FILTER_COLUMN_MAP = {
    "source": COL_SOURCE,
    "type": COL_TYPE,
    "campaign": COL_CAMPAIGN,
    "group_name": COL_GROUP,
    "ad_name": COL_AD,
    "keyword": COL_KEYWORD,
    "region": COL_REGION,
    "device": COL_DEVICE,
    "placement": COL_PLACEMENT,
    "position": COL_POSITION,
    "url": COL_URL,
    "product": COL_PRODUCT,
}

KPI_ORDER = [
    COL_COST,
    COL_CLICKS,
    COL_LEADS,
    "CPL",
    "CR1",
    COL_SALES,
    "CR2",
    COL_AVG_CHECK,
    COL_REVENUE,
    COL_MARGIN,
    "ROMI",
]


def _repair_text(value: object, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    if not text:
        return default

    candidates = {text}
    for source_encoding in ("cp1251", "latin1"):
        for target_encoding in ("utf-8", "cp1251"):
            if source_encoding == target_encoding:
                continue
            try:
                repaired = text.encode(source_encoding, errors="ignore").decode(target_encoding, errors="ignore").strip()
                if repaired:
                    candidates.add(repaired)
            except Exception:
                pass

    def score(candidate: str) -> int:
        cyr = len(re.findall("[\u0410-\u042f\u0430-\u044f\u0401\u0451]", candidate))
        lat = len(re.findall(r"[A-Za-z]", candidate))
        num = len(re.findall(r"[0-9]", candidate))
        spaces = len(re.findall(r"[\s.,:;()\-]", candidate))
        bad = len(re.findall("[\u00d0\u00d1\u00c3\u00cd\u00c2\u00c8\u00d2\u201c\u201d\u2020\u2039\u00bb\u00b1\u0402\u0405\u0406\u0408\u0409\u040a\u040b\u040c\u040f\u0452\u0455\u0456\u0458\u0459\u045a\u045b\u045f]", candidate))
        return cyr * 4 + lat + num + spaces - bad * 3

    best = sorted(candidates, key=score, reverse=True)[0]
    return best or default


def _label(value: str, fallback: str) -> str:
    return _repair_text(value, fallback) or fallback


def slugify_project_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-Я_-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


def ensure_unique_project_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 2
    while db.scalar(select(Project).where(Project.slug == slug)) is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _parse_import_date(value: str) -> datetime:
    cleaned = str(value).strip()
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y",
        "%d.%m.%y",
        "%d.%m.%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise ProjectServiceError(f"Не удалось распознать дату: {value}") from exc


def create_project(db: Session, owner: User, name: str, slug: str | None = None) -> Project:
    base_slug = slugify_project_name(slug or name)
    final_slug = ensure_unique_project_slug(db, base_slug)

    default_owner = _get_primary_owner_user(db)
    project = Project(name=name.strip(), slug=final_slug, status="active", owner_user_id=default_owner.id)
    db.add(project)
    db.flush()

    _get_or_create_project_membership(db, project.id, default_owner.id, "owner")
    if owner.id != default_owner.id:
        _get_or_create_project_membership(db, project.id, owner.id, "editor")

    db.commit()
    db.refresh(project)
    return project

def delete_project(db: Session, current_user: User, project_id: int) -> None:
    project = get_project_for_user(db, current_user, project_id)

    if current_user.role != "admin" and project.owner_user_id != current_user.id:
        raise ProjectAccessDeniedError("Only project owner or admin can delete this project")

    db.delete(project)
    db.commit()
def get_project_for_user(db: Session, current_user: User, project_id: int) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise ProjectNotFoundError("Project not found")

    if current_user.role == "admin":
        return project

    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise ProjectAccessDeniedError("You do not have access to this project")
    return project



def _get_project_membership(db: Session, project_id: int, user_id: int) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )


def _ensure_can_manage_project_content(db: Session, project: Project, current_user: User) -> None:
    if current_user.role == "admin":
        return
    if project.owner_user_id == current_user.id:
        return

    membership = _get_project_membership(db, project.id, current_user.id)
    if membership and membership.role in {"owner", "editor"}:
        return

    raise ProjectAccessDeniedError("Only project editor, owner or admin can modify this project")
def assign_user_to_project(db: Session, current_user: User, project_id: int, email: str, role: str) -> ProjectMember:
    project = get_project_for_user(db, current_user, project_id)

    if current_user.role != "admin" and project.owner_user_id != current_user.id:
        raise ProjectAccessDeniedError("Only project owner or admin can assign users")

    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None:
        raise UserNotFoundError("User not found")

    existing = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise ProjectMemberAlreadyExistsError("User already assigned to this project")

    normalized_role = role.strip().lower()
    if normalized_role == "owner":
        if not _is_primary_owner_user(current_user):
            raise ProjectAccessDeniedError("Only Dmitry can assign project owner")
        membership = ProjectMember(project_id=project_id, user_id=user.id, role="owner")
        db.add(membership)
        db.flush()
        _set_project_owner(db, project, user)
        db.commit()
        db.refresh(membership)
        return membership

    membership = ProjectMember(project_id=project_id, user_id=user.id, role=normalized_role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership

def import_project_data(db: Session, current_user: User, project_id: int, payload: ProjectDataImportRequest) -> ProjectDataImportResult:
    get_project_for_user(db, current_user, project_id)

    if payload.replace_existing:
        db.execute(delete(AdsRawData).where(AdsRawData.project_id == project_id))
        db.execute(delete(CrmRawData).where(CrmRawData.project_id == project_id))

    ads_rows_to_add: list[AdsRawData] = []
    for row in payload.ads_rows:
        row_data = row.model_dump() if isinstance(row, AdsImportRow) else row
        ads_rows_to_add.append(
            AdsRawData(
                project_id=project_id,
                date=_parse_import_date(row_data["date"]),
                source=row_data.get("source", "Не указано"),
                medium=row_data.get("medium", "Не указано"),
                campaign=row_data.get("campaign", "(не указано)"),
                group_name=row_data.get("group_name", "(не указано)"),
                ad_name=row_data.get("ad_name", "(не указано)"),
                keyword=row_data.get("keyword", "(не указано)"),
                region=row_data.get("region", "(не указано)"),
                device=row_data.get("device", "(не указано)"),
                placement=row_data.get("placement", "(не указано)"),
                position=row_data.get("position", "(не указано)"),
                url=row_data.get("url", "(не указано)"),
                product=row_data.get("product", "(не указано)"),
                cost=float(row_data.get("cost", 0) or 0),
                impressions=int(row_data.get("impressions", 0) or 0),
                clicks=int(row_data.get("clicks", 0) or 0),
            )
        )

    crm_rows_to_add: list[CrmRawData] = []
    for row in payload.crm_rows:
        row_data = row.model_dump() if isinstance(row, CrmImportRow) else row
        crm_rows_to_add.append(
            CrmRawData(
                project_id=project_id,
                date=_parse_import_date(row_data["date"]),
                source=row_data.get("source", "Не указано"),
                medium=row_data.get("medium", "Не указано"),
                campaign=row_data.get("campaign", "(не указано)"),
                group_name=row_data.get("group_name", "(не указано)"),
                ad_name=row_data.get("ad_name", "(не указано)"),
                keyword=row_data.get("keyword", "(не указано)"),
                region=row_data.get("region", "(не указано)"),
                device=row_data.get("device", "(не указано)"),
                placement=row_data.get("placement", "(не указано)"),
                position=row_data.get("position", "(не указано)"),
                url=row_data.get("url", "(не указано)"),
                product=row_data.get("product", "(не указано)"),
                leads=int(row_data.get("leads", 0) or 0),
                sales=int(row_data.get("sales", 0) or 0),
                revenue=float(row_data.get("revenue", 0) or 0),
            )
        )

    if ads_rows_to_add:
        db.add_all(ads_rows_to_add)
    if crm_rows_to_add:
        db.add_all(crm_rows_to_add)

    db.commit()

    return ProjectDataImportResult(
        project_id=project_id,
        ads_rows_imported=len(ads_rows_to_add),
        crm_rows_imported=len(crm_rows_to_add),
        replace_existing=payload.replace_existing,
    )


def _build_ads_dataframe(db: Session, project_id: int) -> pd.DataFrame:
    ads_rows = db.scalars(
        select(AdsRawData).where(AdsRawData.project_id == project_id).order_by(AdsRawData.date.asc(), AdsRawData.id.asc())
    ).all()
    if not ads_rows:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                COL_DATE: row.date,
                COL_SOURCE: row.source,
                COL_MEDIUM: row.medium,
                COL_TYPE: row.medium,
                COL_CAMPAIGN: row.campaign,
                COL_GROUP: row.group_name,
                COL_AD: row.ad_name,
                COL_KEYWORD: row.keyword,
                COL_REGION: row.region,
                COL_DEVICE: row.device,
                COL_PLACEMENT: row.placement,
                COL_POSITION: row.position,
                COL_URL: row.url,
                COL_PRODUCT: row.product,
                COL_COST: row.cost,
                COL_IMPRESSIONS: row.impressions,
                COL_CLICKS: row.clicks,
            }
            for row in ads_rows
        ]
    )


def _build_crm_dataframe(db: Session, project_id: int) -> pd.DataFrame:
    crm_rows = db.scalars(
        select(CrmRawData).where(CrmRawData.project_id == project_id).order_by(CrmRawData.date.asc(), CrmRawData.id.asc())
    ).all()
    if not crm_rows:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                COL_DATE: row.date,
                COL_SOURCE: row.source,
                COL_MEDIUM: row.medium,
                COL_TYPE: row.medium,
                COL_CAMPAIGN: row.campaign,
                COL_GROUP: row.group_name,
                COL_AD: row.ad_name,
                COL_KEYWORD: row.keyword,
                COL_REGION: row.region,
                COL_DEVICE: row.device,
                COL_PLACEMENT: row.placement,
                COL_POSITION: row.position,
                COL_URL: row.url,
                COL_PRODUCT: row.product,
                COL_LEADS: row.leads,
                COL_SALES: row.sales,
                COL_REVENUE: row.revenue,
            }
            for row in crm_rows
        ]
    )


def _format_int(value: float | int) -> str:
    return f"{float(value):,.0f}".replace(",", " ")


def _format_percent(value: float) -> str:
    return f"{float(value):.2f}%".replace(".", ",")


def _build_date_table_rows(merged_df: pd.DataFrame, limit: int = 31) -> list[DashboardTableRowRead]:
    if merged_df is None or merged_df.empty:
        return []

    grouped = (
        merged_df.groupby(COL_DATE, dropna=False)
        .agg({
            COL_COST: "sum",
            COL_IMPRESSIONS: "sum",
            COL_CLICKS: "sum",
            COL_LEADS: "sum",
            COL_SALES: "sum",
            COL_REVENUE: "sum",
            COL_MARGIN: "sum",
        })
        .reset_index()
        .sort_values(COL_DATE)
    )

    grouped["CPC"] = grouped.apply(lambda row: (row[COL_COST] / row[COL_CLICKS]) if row[COL_CLICKS] > 0 else 0, axis=1)
    grouped["CTR"] = grouped.apply(lambda row: (row[COL_CLICKS] / row[COL_IMPRESSIONS] * 100) if row[COL_IMPRESSIONS] > 0 else 0, axis=1)
    grouped["CPL"] = grouped.apply(lambda row: (row[COL_COST] / row[COL_LEADS]) if row[COL_LEADS] > 0 else 0, axis=1)
    grouped["CR1"] = grouped.apply(lambda row: (row[COL_LEADS] / row[COL_CLICKS] * 100) if row[COL_CLICKS] > 0 else 0, axis=1)
    grouped["CR2"] = grouped.apply(lambda row: (row[COL_SALES] / row[COL_LEADS] * 100) if row[COL_LEADS] > 0 else 0, axis=1)
    grouped[COL_AVG_CHECK] = grouped.apply(lambda row: (row[COL_REVENUE] / row[COL_SALES]) if row[COL_SALES] > 0 else 0, axis=1)
    grouped["ROMI"] = grouped.apply(lambda row: ((row[COL_MARGIN] / row[COL_COST]) * 100) if row[COL_COST] > 0 else -100, axis=1)

    rows: list[DashboardTableRowRead] = []
    for _, row in grouped.head(limit).iterrows():
        rows.append(
            DashboardTableRowRead(
                values=[
                    row[COL_DATE].strftime("%d.%m.%Y"),
                    _format_int(row[COL_COST]),
                    _format_int(row[COL_IMPRESSIONS]),
                    _format_int(row[COL_CLICKS]),
                    _format_int(row["CPC"]),
                    _format_percent(row["CTR"]),
                    _format_int(row[COL_LEADS]),
                    _format_int(row["CPL"]),
                    _format_percent(row["CR1"]),
                    _format_int(row[COL_SALES]),
                    _format_percent(row["CR2"]),
                    _format_int(row[COL_AVG_CHECK]),
                    _format_int(row[COL_REVENUE]),
                    _format_int(row[COL_MARGIN]),
                    _format_percent(row["ROMI"]),
                ]
            )
        )

    total = calculate_kpi_metrics(merged_df)
    rows.append(
        DashboardTableRowRead(
            values=[
                "ИТОГО",
                _format_int(total[COL_COST]),
                _format_int(float(merged_df[COL_IMPRESSIONS].sum())),
                _format_int(total[COL_CLICKS]),
                _format_int(float(total[COL_COST] / total[COL_CLICKS]) if total[COL_CLICKS] > 0 else 0),
                _format_percent(float((merged_df[COL_CLICKS].sum() / merged_df[COL_IMPRESSIONS].sum() * 100) if merged_df[COL_IMPRESSIONS].sum() > 0 else 0)),
                _format_int(total[COL_LEADS]),
                _format_int(total["CPL"]),
                _format_percent(total["CR1"]),
                _format_int(total[COL_SALES]),
                _format_percent(total["CR2"]),
                _format_int(total[COL_AVG_CHECK]),
                _format_int(total[COL_REVENUE]),
                _format_int(total[COL_MARGIN]),
                _format_percent(total["ROMI"]),
            ],
            is_total=True,
        )
    )
    return rows


def _build_filter_options(merged_df: pd.DataFrame) -> list[DashboardFilterOptionRead]:
    if merged_df is None or merged_df.empty:
        return []

    result: list[DashboardFilterOptionRead] = []
    for key, column in FILTER_COLUMN_MAP.items():
        if column not in merged_df.columns:
            continue
        options = sorted({_repair_text(value, "") for value in merged_df[column].dropna().tolist() if _repair_text(value, "")})
        result.append(DashboardFilterOptionRead(key=key, label=_label(column, key), options=options))
    return result


def _build_dashboard_records(merged_df: pd.DataFrame) -> list[DashboardRecordRead]:
    if merged_df is None or merged_df.empty:
        return []

    records: list[DashboardRecordRead] = []
    for _, row in merged_df.iterrows():
        records.append(
            DashboardRecordRead(
                date=row[COL_DATE].strftime("%d.%m.%Y"),                source=_repair_text(row.get(COL_SOURCE, "Не указано"), "Не указано"),
                type=_repair_text(row.get(COL_TYPE, "Не указано"), "Не указано"),
                medium=_repair_text(row.get(COL_MEDIUM, row.get(COL_TYPE, "Не указано")), "Не указано"),
                campaign=_repair_text(row.get(COL_CAMPAIGN, "(не указано)"), "(не указано)"),
                group_name=_repair_text(row.get(COL_GROUP, "(не указано)"), "(не указано)"),
                ad_name=_repair_text(row.get(COL_AD, "(не указано)"), "(не указано)"),
                keyword=_repair_text(row.get(COL_KEYWORD, "(не указано)"), "(не указано)"),
                region=_repair_text(row.get(COL_REGION, "(не указано)"), "(не указано)"),
                device=_repair_text(row.get(COL_DEVICE, "(не указано)"), "(не указано)"),
                placement=_repair_text(row.get(COL_PLACEMENT, "(не указано)"), "(не указано)"),
                position=_repair_text(row.get(COL_POSITION, "(не указано)"), "(не указано)"),
                url=_repair_text(row.get(COL_URL, "(не указано)"), "(не указано)"),
                product=_repair_text(row.get(COL_PRODUCT, "(не указано)"), "(не указано)"),
                cost=float(row.get(COL_COST, 0) or 0),
                impressions=int(row.get(COL_IMPRESSIONS, 0) or 0),
                clicks=int(row.get(COL_CLICKS, 0) or 0),
                cpc=float(row.get("CPC", 0) or 0),
                ctr=float(row.get("CTR", 0) or 0),
                leads=int(row.get(COL_LEADS, 0) or 0),
                cpl=float(row.get("CPL", 0) or 0),
                cr1=float(row.get("CR1", 0) or 0),
                sales=int(row.get(COL_SALES, 0) or 0),
                cr2=float(row.get("CR2", 0) or 0),
                avg_check=float(row.get(COL_AVG_CHECK, 0) or 0),
                revenue=float(row.get(COL_REVENUE, 0) or 0),
                margin=float(row.get(COL_MARGIN, 0) or 0),
                romi=float(row.get("ROMI", -100) or -100),
            )
        )
    return records


def build_project_dashboard_summary(db: Session, project: Project) -> ProjectDashboardRead:
    ads_count = db.scalar(select(func.count()).select_from(AdsRawData).where(AdsRawData.project_id == project.id)) or 0
    crm_count = db.scalar(select(func.count()).select_from(CrmRawData).where(CrmRawData.project_id == project.id)) or 0

    ads_df = _build_ads_dataframe(db, project.id)
    crm_df = _build_crm_dataframe(db, project.id)
    merged_df, _, _, _ = build_merged_dataframe_from_sources(ads_df, crm_df)

    if not merged_df.empty:
        period_start = merged_df[COL_DATE].min()
        period_end = merged_df[COL_DATE].max()
        period_label = f"{period_start:%d.%m.%Y} - {period_end:%d.%m.%Y}"
        kpi_metrics = calculate_kpi_metrics(merged_df)
        formatted_metrics = format_kpi_values(kpi_metrics)
        metrics = [DashboardMetricRead(label=label, value=formatted_metrics[label]) for label in KPI_ORDER]
        headers = [COL_DATE, COL_COST, COL_IMPRESSIONS, COL_CLICKS, "CPC", "CTR", COL_LEADS, "CPL", "CR1", COL_SALES, "CR2", COL_AVG_CHECK, COL_REVENUE, COL_MARGIN, "ROMI"]
        rows = _build_date_table_rows(merged_df)
        filter_options = _build_filter_options(merged_df)
        records = _build_dashboard_records(merged_df)
    else:
        min_ads_date = db.scalar(select(func.min(AdsRawData.date)).where(AdsRawData.project_id == project.id))
        max_ads_date = db.scalar(select(func.max(AdsRawData.date)).where(AdsRawData.project_id == project.id))
        min_crm_date = db.scalar(select(func.min(CrmRawData.date)).where(CrmRawData.project_id == project.id))
        max_crm_date = db.scalar(select(func.max(CrmRawData.date)).where(CrmRawData.project_id == project.id))
        period_start = min([date for date in [min_ads_date, min_crm_date] if date is not None], default=None)
        period_end = max([date for date in [max_ads_date, max_crm_date] if date is not None], default=None)
        period_label = f"{period_start:%d.%m.%Y} - {period_end:%d.%m.%Y}" if period_start and period_end else "Период пока не определен"
        zero_metrics = format_kpi_values(calculate_kpi_metrics(pd.DataFrame()))
        metrics = [DashboardMetricRead(label=label, value=zero_metrics[label]) for label in KPI_ORDER]
        headers = ["Показатель", "Значение"]
        rows = [
            DashboardTableRowRead(values=["Рекламных строк", str(int(ads_count))]),
            DashboardTableRowRead(values=["CRM строк", str(int(crm_count))]),
        ]
        filter_options = []
        records = []

    return ProjectDashboardRead(
        project=ProjectRead.model_validate(project),
        period_label=period_label,
        filters=[
            "Источник: Все",
            "Тип: Все",
            f"Рекламных строк: {int(ads_count)}",
            f"CRM строк: {int(crm_count)}",
        ],
        metrics=metrics,
        table_headers=headers,
        table_rows=rows,
        filter_options=filter_options,
        records=records,
    )


def list_project_plans(db: Session, current_user: User, project_id: int) -> list[ProjectPlanRead]:
    get_project_for_user(db, current_user, project_id)
    plans = db.scalars(
        select(ProjectPlan).where(ProjectPlan.project_id == project_id).order_by(ProjectPlan.period_from.desc(), ProjectPlan.created_at.desc(), ProjectPlan.id.desc())
    ).all()
    return [ProjectPlanRead.model_validate(plan) for plan in plans]


def upsert_project_plan(db: Session, current_user: User, project_id: int, payload: ProjectPlanUpsertRequest) -> ProjectPlanRead:
    get_project_for_user(db, current_user, project_id)

    if payload.period_to < payload.period_from:
        raise ProjectServiceError("Дата окончания плана не может быть раньше даты начала")

    existing = db.scalar(
        select(ProjectPlan).where(
            ProjectPlan.project_id == project_id,
            ProjectPlan.period_from == payload.period_from,
            ProjectPlan.period_to == payload.period_to,
            ProjectPlan.product == payload.product.strip(),
            ProjectPlan.source == payload.source.strip(),
            ProjectPlan.type == payload.type.strip(),
        )
    )

    if existing is None:
        existing = ProjectPlan(
            project_id=project_id,
            period_from=payload.period_from,
            period_to=payload.period_to,
            product=payload.product.strip() or "Все",
            source=payload.source.strip() or "Все",
            type=payload.type.strip() or "Все",
            budget=float(payload.budget or 0),
            leads=int(payload.leads or 0),
        )
        db.add(existing)
    else:
        existing.budget = float(payload.budget or 0)
        existing.leads = int(payload.leads or 0)
        existing.product = payload.product.strip() or "Все"
        existing.source = payload.source.strip() or "Все"
        existing.type = payload.type.strip() or "Все"

    db.commit()
    db.refresh(existing)
    return ProjectPlanRead.model_validate(existing)


def delete_project_plan(db: Session, current_user: User, project_id: int, plan_id: int) -> None:
    get_project_for_user(db, current_user, project_id)
    plan = db.scalar(select(ProjectPlan).where(ProjectPlan.id == plan_id, ProjectPlan.project_id == project_id))
    if plan is None:
        raise ProjectNotFoundError("Plan not found")
    db.delete(plan)
    db.commit()










def _ensure_can_manage_project_access(project: Project, current_user: User) -> None:
    if current_user.role == "admin":
        return
    if project.owner_user_id == current_user.id:
        return
    raise ProjectAccessDeniedError("Only project owner or admin can manage project access")


def list_project_members(db: Session, current_user: User, project_id: int) -> list[ProjectMember]:
    project = get_project_for_user(db, current_user, project_id)
    _ensure_can_manage_project_access(project, current_user)
    return db.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc(), ProjectMember.id.asc())
    ).all()


def update_project_member_role(db: Session, current_user: User, project_id: int, member_id: int, role: str) -> ProjectMember:
    project = get_project_for_user(db, current_user, project_id)
    _ensure_can_manage_project_access(project, current_user)
    membership = db.scalar(
        select(ProjectMember).where(ProjectMember.id == member_id, ProjectMember.project_id == project_id)
    )
    if membership is None:
        raise ProjectMemberNotFoundError("Project member not found")

    normalized_role = role.strip().lower()
    is_current_owner = project.owner_user_id == membership.user_id

    if normalized_role == "owner":
        if not _is_primary_owner_user(current_user):
            raise ProjectAccessDeniedError("Only Dmitry can assign project owner")
        membership.role = "owner"
        _set_project_owner(db, project, membership.user)
        db.commit()
        db.refresh(membership)
        return membership

    if is_current_owner:
        if not _is_primary_owner_user(current_user):
            raise ProjectAccessDeniedError("Only Dmitry can change project owner")
        primary_owner = _get_primary_owner_user(db)
        membership.role = normalized_role
        _set_project_owner(db, project, primary_owner)
        if membership.user_id == primary_owner.id:
            membership.role = normalized_role
            project.owner_user_id = primary_owner.id
        db.commit()
        db.refresh(membership)
        return membership

    membership.role = normalized_role
    db.commit()
    db.refresh(membership)
    return membership

def remove_project_member(db: Session, current_user: User, project_id: int, member_id: int) -> None:
    project = get_project_for_user(db, current_user, project_id)
    _ensure_can_manage_project_access(project, current_user)
    membership = db.scalar(
        select(ProjectMember).where(ProjectMember.id == member_id, ProjectMember.project_id == project_id)
    )
    if membership is None:
        raise ProjectMemberNotFoundError("Project member not found")
    if project.owner_user_id == membership.user_id:
        raise ProjectServiceError("Project owner cannot be removed from access list")
    db.delete(membership)
    db.commit()
