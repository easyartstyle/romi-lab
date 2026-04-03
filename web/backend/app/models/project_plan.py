from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ProjectPlan(Base):
    __tablename__ = "project_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    period_from: Mapped[datetime.date] = mapped_column(Date, index=True)
    period_to: Mapped[datetime.date] = mapped_column(Date, index=True)
    product: Mapped[str] = mapped_column(String(255), default="Все")
    source: Mapped[str] = mapped_column(String(255), default="Все")
    type: Mapped[str] = mapped_column(String(255), default="Все")
    budget: Mapped[float] = mapped_column(default=0)
    leads: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="plans")

