from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    future=True,
    echo=False,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    required_columns = {
        "ads_raw_data": {
            "region": "TEXT DEFAULT '(?? ???????)'",
            "device": "TEXT DEFAULT '(?? ???????)'",
            "placement": "TEXT DEFAULT '(?? ???????)'",
            "position": "TEXT DEFAULT '(?? ???????)'",
            "url": "TEXT DEFAULT '(?? ???????)'",
            "product": "TEXT DEFAULT '(?? ???????)'",
        },
        "crm_raw_data": {
            "region": "TEXT DEFAULT '(?? ???????)'",
            "device": "TEXT DEFAULT '(?? ???????)'",
            "placement": "TEXT DEFAULT '(?? ???????)'",
            "position": "TEXT DEFAULT '(?? ???????)'",
            "url": "TEXT DEFAULT '(?? ???????)'",
            "product": "TEXT DEFAULT '(?? ???????)'",
        },
        "project_plans": {
            "product": "TEXT DEFAULT ''Все''",
        },
    }
    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()}
            for column_name, column_sql in columns.items():
                if column_name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")



