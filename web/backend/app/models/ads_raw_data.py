from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AdsRawData(Base):
    __tablename__ = "ads_raw_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(String(255), default="Не указано")
    medium: Mapped[str] = mapped_column(String(255), default="Не указано")
    campaign: Mapped[str] = mapped_column(String(255), default="(не указано)")
    group_name: Mapped[str] = mapped_column(String(255), default="(не указано)")
    ad_name: Mapped[str] = mapped_column(String(255), default="(не указано)")
    keyword: Mapped[str] = mapped_column(String(255), default="(не указано)")
    region: Mapped[str] = mapped_column(String(255), default="(не указано)")
    device: Mapped[str] = mapped_column(String(255), default="(не указано)")
    placement: Mapped[str] = mapped_column(String(255), default="(не указано)")
    position: Mapped[str] = mapped_column(String(255), default="(не указано)")
    url: Mapped[str] = mapped_column(String(1024), default="(не указано)")
    product: Mapped[str] = mapped_column(String(255), default="(не указано)")
    cost: Mapped[float] = mapped_column(Float, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="ads_rows")
