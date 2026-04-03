from __future__ import annotations

import pandas as pd


def calculate_kpi_metrics(data: pd.DataFrame | None) -> dict[str, float]:
    if data is None or data.empty:
        return {
            "Расход": 0.0,
            "Клики": 0.0,
            "Лиды": 0.0,
            "Продажи": 0.0,
            "Выручка": 0.0,
            "CPL": 0.0,
            "CR1": 0.0,
            "CR2": 0.0,
            "Ср.чек": 0.0,
            "Маржа": 0.0,
            "ROMI": -100.0,
        }

    total_expense = pd.to_numeric(data["Расход"], errors="coerce").fillna(0).sum() if "Расход" in data.columns else 0.0
    total_clicks = pd.to_numeric(data["Клики"], errors="coerce").fillna(0).sum() if "Клики" in data.columns else 0.0
    total_leads = pd.to_numeric(data["Лиды"], errors="coerce").fillna(0).sum() if "Лиды" in data.columns else 0.0
    total_sales = pd.to_numeric(data["Продажи"], errors="coerce").fillna(0).sum() if "Продажи" in data.columns else 0.0
    total_revenue = pd.to_numeric(data["Выручка"], errors="coerce").fillna(0).sum() if "Выручка" in data.columns else 0.0

    avg_cpl = (total_expense / total_leads) if total_leads > 0 else 0.0
    avg_cr1 = ((total_leads / total_clicks) * 100) if total_clicks > 0 else 0.0
    avg_cr2 = ((total_sales / total_leads) * 100) if total_leads > 0 else 0.0
    avg_check = (total_revenue / total_sales) if total_sales > 0 else 0.0
    total_margin = total_revenue - total_expense
    avg_romi = ((total_margin / total_expense) * 100) if total_expense > 0 else -100.0

    return {
        "Расход": float(total_expense),
        "Клики": float(total_clicks),
        "Лиды": float(total_leads),
        "Продажи": float(total_sales),
        "Выручка": float(total_revenue),
        "CPL": float(avg_cpl),
        "CR1": float(avg_cr1),
        "CR2": float(avg_cr2),
        "Ср.чек": float(avg_check),
        "Маржа": float(total_margin),
        "ROMI": float(avg_romi),
    }


def build_kpi_dataframe_from_metrics(metrics: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Расход": [metrics.get("Расход", 0.0)],
        "Клики": [metrics.get("Клики", 0.0)],
        "Лиды": [metrics.get("Лиды", 0.0)],
        "Продажи": [metrics.get("Продажи", 0.0)],
        "Выручка": [metrics.get("Выручка", 0.0)],
        "Ср.чек": [metrics.get("Ср.чек", 0.0)],
        "Маржа": [metrics.get("Маржа", 0.0)],
        "ROMI": [metrics.get("ROMI", -100.0)],
    })


def format_kpi_values(metrics: dict[str, float]) -> dict[str, str]:
    return {
        "Расход": f"{metrics.get('Расход', 0):,.0f}".replace(",", " "),
        "Клики": f"{metrics.get('Клики', 0):,.0f}".replace(",", " "),
        "Лиды": f"{metrics.get('Лиды', 0):,.0f}".replace(",", " "),
        "CPL": f"{metrics.get('CPL', 0):,.0f}".replace(",", " "),
        "CR1": f"{metrics.get('CR1', 0):.2f}".replace(".", ","),
        "Продажи": f"{metrics.get('Продажи', 0):,.0f}".replace(",", " "),
        "CR2": f"{metrics.get('CR2', 0):.2f}".replace(".", ","),
        "Ср.чек": f"{metrics.get('Ср.чек', 0):,.0f}".replace(",", " "),
        "Выручка": f"{metrics.get('Выручка', 0):,.0f}".replace(",", " "),
        "Маржа": f"{metrics.get('Маржа', 0):,.0f}".replace(",", " "),
        "ROMI": f"{metrics.get('ROMI', -100):.2f}%".replace(".", ","),
    }
