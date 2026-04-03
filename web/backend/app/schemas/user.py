from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)
    is_active: bool | None = None


class UserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="client", min_length=1, max_length=50)
    project_id: int | None = None
    project_role: str | None = Field(default="client", min_length=1, max_length=50)


class UserInviteResponse(BaseModel):
    user: UserRead
    invite_url: str
    project_id: int | None = None
    project_role: str | None = None