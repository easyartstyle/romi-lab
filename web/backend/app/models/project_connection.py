from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ProjectConnection(Base):
    __tablename__ = "project_connections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    category: Mapped[str] = mapped_column(String(50), default="ads", index=True)
    platform: Mapped[str] = mapped_column(String(100), default="yandex_direct")
    name: Mapped[str] = mapped_column(String(255))
    identifier: Mapped[str] = mapped_column(String(255), default="")
    api_mode: Mapped[str] = mapped_column(String(50), default="production")
    client_login_mode: Mapped[str] = mapped_column(String(50), default="auto")
    token: Mapped[str] = mapped_column(Text, default="")
    client_id: Mapped[str] = mapped_column(String(255), default="")
    client_secret: Mapped[str] = mapped_column(String(255), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="not_connected")
    status_comment: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="connections")
