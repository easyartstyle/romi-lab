from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: int
    email: EmailStr
    full_name: str
    role: str
    access_token: str
    token_type: str = "bearer"
    issued_at: datetime


class InviteInfoResponse(BaseModel):
    email: EmailStr
    full_name: str
    role: str


class InviteAcceptRequest(BaseModel):
    token: str
    password: str = Field(min_length=8)