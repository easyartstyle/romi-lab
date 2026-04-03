from datetime import datetime

from pydantic import BaseModel, Field


class ProjectConnectionRead(BaseModel):
    id: int
    project_id: int
    category: str
    platform: str
    name: str
    identifier: str
    api_mode: str
    client_login_mode: str
    token: str
    client_id: str
    client_secret: str
    refresh_token: str
    status: str
    status_comment: str
    checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectConnectionUpsertRequest(BaseModel):
    category: str = Field(default="ads", max_length=50)
    platform: str = Field(default="yandex_direct", max_length=100)
    name: str = Field(min_length=1, max_length=255)
    identifier: str = Field(default="", max_length=255)
    api_mode: str = Field(default="production", max_length=50)
    client_login_mode: str = Field(default="auto", max_length=50)
    token: str = ""
    client_id: str = Field(default="", max_length=255)
    client_secret: str = Field(default="", max_length=255)
    refresh_token: str = ""


class ProjectConnectionTestResult(BaseModel):
    ok: bool
    status: str
    status_comment: str
    checked_at: datetime | None = None
