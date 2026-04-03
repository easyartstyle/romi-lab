from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class ProjectRead(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    owner_user_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)


class ProjectMemberAssignRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", min_length=1, max_length=50)


class ProjectMemberUpdateRequest(BaseModel):
    role: str = Field(default="viewer", min_length=1, max_length=50)


class ProjectMemberRead(BaseModel):
    id: int
    project_id: int
    user_id: int
    role: str
    is_owner: bool = False
    created_at: datetime
    email: EmailStr | None = None
    full_name: str | None = None
    system_role: str | None = None

    model_config = {"from_attributes": True}


class ProjectPlanRead(BaseModel):
    id: int
    project_id: int
    period_from: date
    period_to: date
    product: str
    source: str
    type: str
    budget: float
    leads: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectPlanUpsertRequest(BaseModel):
    period_from: date
    period_to: date
    product: str = Field(default="Все", max_length=255)
    source: str = Field(default="Все", max_length=255)
    type: str = Field(default="Все", max_length=255)
    budget: float = 0
    leads: int = 0


class DashboardMetricRead(BaseModel):
    label: str
    value: str


class DashboardTableRowRead(BaseModel):
    values: list[str]
    is_total: bool = False


class DashboardFilterOptionRead(BaseModel):
    key: str
    label: str
    options: list[str]


class DashboardRecordRead(BaseModel):
    date: str
    source: str
    type: str
    medium: str
    campaign: str
    group_name: str
    ad_name: str
    keyword: str
    region: str
    device: str
    placement: str
    position: str
    url: str
    product: str
    cost: float
    impressions: int
    clicks: int
    cpc: float
    ctr: float
    leads: int
    cpl: float
    cr1: float
    sales: int
    cr2: float
    avg_check: float
    revenue: float
    margin: float
    romi: float


class ProjectDashboardRead(BaseModel):
    project: ProjectRead
    period_label: str
    filters: list[str]
    metrics: list[DashboardMetricRead]
    table_headers: list[str]
    table_rows: list[DashboardTableRowRead]
    filter_options: list[DashboardFilterOptionRead] = Field(default_factory=list)
    records: list[DashboardRecordRead] = Field(default_factory=list)


class AdsImportRow(BaseModel):
    date: str
    source: str = "Не указано"
    medium: str = "Не указано"
    campaign: str = "(не указано)"
    group_name: str = "(не указано)"
    ad_name: str = "(не указано)"
    keyword: str = "(не указано)"
    region: str = "(не указано)"
    device: str = "(не указано)"
    placement: str = "(не указано)"
    position: str = "(не указано)"
    url: str = "(не указано)"
    product: str = "(не указано)"
    cost: float = 0
    impressions: int = 0
    clicks: int = 0


class CrmImportRow(BaseModel):
    date: str
    source: str = "Не указано"
    medium: str = "Не указано"
    campaign: str = "(не указано)"
    group_name: str = "(не указано)"
    ad_name: str = "(не указано)"
    keyword: str = "(не указано)"
    region: str = "(не указано)"
    device: str = "(не указано)"
    placement: str = "(не указано)"
    position: str = "(не указано)"
    url: str = "(не указано)"
    product: str = "(не указано)"
    leads: int = 0
    sales: int = 0
    revenue: float = 0



class ProjectDataImportRequest(BaseModel):
    ads_rows: list[AdsImportRow] = Field(default_factory=list)
    crm_rows: list[CrmImportRow] = Field(default_factory=list)
    replace_existing: bool = True


class ProjectDataImportResult(BaseModel):
    project_id: int
    ads_rows_imported: int
    crm_rows_imported: int
    replace_existing: bool
