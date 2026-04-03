from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


DIMENSION_COLUMNS = ["Источник", "Кампания", "Группа", "Объявление", "Ключевая фраза", "Регион", "Устройство", "Площадка", "Position", "URL", "Продукт"]
TEXT_PLACEHOLDERS = {"", "nan", "none", "null", "nat", "не указано", "(не указано)"}
DIMENSION_DEFAULTS = {
    "Источник": "(не указано)",
    "Кампания": "(не указано)",
    "Группа": "(не указано)",
    "Объявление": "(не указано)",
    "Ключевая фраза": "(не указано)",
    "Регион": "(не указано)",
    "Устройство": "(не указано)",
    "Площадка": "(не указано)",
    "Position": "(не указано)",
    "URL": "(не указано)",
    "Продукт": "(не указано)",
    "Medium": "Не указано",
    "Тип": "Не указано",
}


def _default_parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce")


def normalize_text_dimension_series(series: pd.Series, default_value: str) -> pd.Series:
    cleaned = series.fillna("").astype(str).str.strip()
    return cleaned.apply(
        lambda value: default_value if value.strip().lower() in TEXT_PLACEHOLDERS else value.strip()
    )


def normalize_source_dataframe(
    df: pd.DataFrame | None,
    source_type: str,
    date_parser: Callable[[pd.Series], pd.Series] | None = None,
) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    normalized.columns = [str(col).strip() for col in normalized.columns]

    if "Тип" in normalized.columns and "Medium" not in normalized.columns:
        normalized["Medium"] = normalized["Тип"]
    elif "Medium" in normalized.columns and "Тип" not in normalized.columns:
        normalized["Тип"] = normalized["Medium"]

    if "Дата" not in normalized.columns:
        return pd.DataFrame()

    parser = date_parser or _default_parse_date_series
    try:
        normalized["Дата"] = parser(normalized["Дата"])
    except Exception:
        normalized["Дата"] = _default_parse_date_series(normalized["Дата"])
    normalized = normalized.dropna(subset=["Дата"]).copy()

    for col, default_value in DIMENSION_DEFAULTS.items():
        if col not in normalized.columns:
            normalized[col] = default_value
        else:
            normalized[col] = normalize_text_dimension_series(normalized[col], default_value)

    for col in ["Расход", "Показы", "Клики", "Лиды", "Продажи", "Выручка", "Ср.чек"]:
        if col not in normalized.columns:
            normalized[col] = 0
        normalized[col] = pd.to_numeric(normalized[col], errors="coerce").fillna(0)

    if source_type == "ads":
        for col in ["Лиды", "Продажи", "Выручка", "Ср.чек"]:
            if col not in df.columns:
                normalized[col] = 0
    elif source_type == "crm":
        for col in ["Расход", "Показы", "Клики"]:
            if col not in df.columns:
                normalized[col] = 0
        if "Выручка" not in df.columns and {"Продажи", "Ср.чек"}.issubset(normalized.columns):
            normalized["Выручка"] = (
                pd.to_numeric(normalized["Продажи"], errors="coerce").fillna(0)
                * pd.to_numeric(normalized["Ср.чек"], errors="coerce").fillna(0)
            )
        if {"Выручка", "Продажи"}.issubset(normalized.columns):
            normalized["Ср.чек"] = np.where(
                pd.to_numeric(normalized["Продажи"], errors="coerce").fillna(0) > 0,
                pd.to_numeric(normalized["Выручка"], errors="coerce").fillna(0)
                / pd.to_numeric(normalized["Продажи"], errors="coerce").fillna(0),
                0,
            )

    return normalized.sort_values("Дата").reset_index(drop=True)


def fill_missing_crm_dimensions_from_ads(
    crm_df: pd.DataFrame | None,
    ads_df: pd.DataFrame | None,
    dimension_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, int]:
    if crm_df is None or crm_df.empty or ads_df is None or ads_df.empty:
        return crm_df.copy() if isinstance(crm_df, pd.DataFrame) else pd.DataFrame(), 0

    cols = dimension_cols or DIMENSION_COLUMNS
    crm_filled = crm_df.copy()
    filled_counter = 0
    missing_values = {"", "(не указано)", "не указано"}

    for idx, crm_row in crm_filled.iterrows():
        candidates = ads_df[ads_df["Дата"] == crm_row["Дата"]]
        if candidates.empty:
            continue

        for known_col in cols:
            if known_col not in crm_filled.columns or known_col not in candidates.columns:
                continue
            crm_value = str(crm_row.get(known_col, "")).strip()
            if crm_value and crm_value.lower() not in missing_values:
                candidates = candidates[candidates[known_col].astype(str).str.strip() == crm_value]
                if candidates.empty:
                    break

        if candidates.empty:
            continue

        for target_col in cols:
            crm_value = str(crm_filled.at[idx, target_col]).strip() if target_col in crm_filled.columns else ""
            if crm_value.lower() not in missing_values:
                continue

            unique_values = candidates[target_col].dropna().astype(str).str.strip()
            unique_values = [value for value in unique_values.unique().tolist() if value and value.lower() not in missing_values]
            if len(unique_values) == 1:
                crm_filled.at[idx, target_col] = unique_values[0]
                filled_counter += 1

    return crm_filled, filled_counter


def build_merged_dataframe_from_sources(
    ads_data: pd.DataFrame | None,
    crm_data: pd.DataFrame | None,
    date_parser: Callable[[pd.Series], pd.Series] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    if ads_data is None or ads_data.empty or crm_data is None or crm_data.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), 0

    ads_df = normalize_source_dataframe(ads_data, "ads", date_parser=date_parser)
    crm_df = normalize_source_dataframe(crm_data, "crm", date_parser=date_parser)

    if ads_df.empty or crm_df.empty:
        return pd.DataFrame(), ads_df, crm_df, 0

    crm_df, filled_counter = fill_missing_crm_dimensions_from_ads(crm_df, ads_df, DIMENSION_COLUMNS)
    merge_cols = ["Дата"] + DIMENSION_COLUMNS

    ads_grouped = (
        ads_df.groupby(merge_cols, dropna=False)
        .agg({"Расход": "sum", "Показы": "sum", "Клики": "sum"})
        .reset_index()
    )

    crm_df["__crm_revenue"] = pd.to_numeric(crm_df.get("Выручка", 0), errors="coerce").fillna(0)
    crm_grouped = (
        crm_df.groupby(merge_cols, dropna=False)
        .agg({"Лиды": "sum", "Продажи": "sum", "__crm_revenue": "sum"})
        .reset_index()
    )
    crm_grouped["Ср.чек"] = np.where(
        crm_grouped["Продажи"] > 0,
        crm_grouped["__crm_revenue"] / crm_grouped["Продажи"],
        0,
    )

    merged = pd.merge(ads_grouped, crm_grouped, on=merge_cols, how="outer")

    for col in ["Расход", "Показы", "Клики", "Лиды", "Продажи", "__crm_revenue", "Ср.чек"]:
        if col not in merged.columns:
            merged[col] = 0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    for col in DIMENSION_COLUMNS:
        if col not in merged.columns:
            merged[col] = "(не указано)"
        merged[col] = merged[col].fillna("(не указано)").astype(str).replace("", "(не указано)")

    merged["Medium"] = "Не указано"
    if "Medium" in ads_df.columns:
        ads_medium_map = ads_df[merge_cols + ["Medium"]].drop_duplicates(subset=merge_cols, keep="first")
        merged = merged.merge(ads_medium_map, on=merge_cols, how="left", suffixes=("", "_ads"))
        if "Medium_ads" in merged.columns:
            merged["Medium"] = merged["Medium_ads"].fillna(merged["Medium"])
            merged = merged.drop(columns=["Medium_ads"])

    if "Medium" in crm_df.columns:
        crm_medium_map = crm_df[merge_cols + ["Medium"]].drop_duplicates(subset=merge_cols, keep="first")
        merged = merged.merge(crm_medium_map, on=merge_cols, how="left", suffixes=("", "_crm"))
        if "Medium_crm" in merged.columns:
            merged["Medium"] = merged["Medium"].where(
                merged["Medium"].astype(str).str.strip().ne("Не указано"),
                merged["Medium_crm"],
            )
            merged = merged.drop(columns=["Medium_crm"])

    merged["Medium"] = merged["Medium"].fillna("Не указано").astype(str).replace("", "Не указано")
    merged["Тип"] = merged["Medium"]
    merged["Выручка"] = merged["__crm_revenue"].round(0)
    merged["CTR"] = np.where(merged["Показы"] > 0, merged["Клики"] / merged["Показы"] * 100, 0).round(2)
    merged["CR1"] = np.where(merged["Клики"] > 0, merged["Лиды"] / merged["Клики"] * 100, 0).round(2)
    merged["CPC"] = np.where(merged["Клики"] > 0, merged["Расход"] / merged["Клики"], 0).round(0)
    merged["CPL"] = np.where(merged["Лиды"] > 0, merged["Расход"] / merged["Лиды"], 0).round(0)
    merged["CR2"] = np.where(merged["Лиды"] > 0, merged["Продажи"] / merged["Лиды"] * 100, 0).round(2)
    merged["Маржа"] = (merged["Выручка"] - merged["Расход"]).round(0)
    merged["ROMI"] = np.where(
        merged["Расход"] > 0,
        ((merged["Выручка"] - merged["Расход"]) / merged["Расход"]) * 100,
        -100,
    ).round(2)

    for int_col in ["Показы", "Клики", "Лиды", "Продажи", "CPC", "CPL"]:
        merged[int_col] = pd.to_numeric(merged[int_col], errors="coerce").fillna(0).round(0).astype(int)
    for money_col in ["Расход", "Ср.чек", "Выручка", "Маржа"]:
        merged[money_col] = pd.to_numeric(merged[money_col], errors="coerce").fillna(0).round(0)

    merged = merged.drop(columns=["__crm_revenue"], errors="ignore")
    merged = merged.sort_values("Дата").reset_index(drop=True)
    return merged, ads_df, crm_df, filled_counter

