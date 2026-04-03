// @ts-nocheck
"use client";

/* __next_internal_client_entry_do_not_use__ default auto */ import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as XLSX from "xlsx";
import { deleteProjectPlan, deleteProjectConnection, fetchProjectDashboard, fetchProjectConnections, fetchProjectMembers, fetchProjectPlans, getStoredToken, getStoredUser, importProjectData, saveProjectConnection, saveProjectPlan, testProjectConnection } from "@/lib/api";
import ImportFileCard from "@/components/import-file-card";
import { ADS_IMPORT_FIELDS, CRM_IMPORT_FIELDS, inferImportMapping, remapImportedRows } from "@/lib/import-mapping";
const TABS = [
    {
        key: "date",
        label: "Дата",
        field: "date"
    },
    {
        key: "source",
        label: "Источник",
        field: "source"
    },
    {
        key: "type",
        label: "Тип",
        field: "type"
    },
    {
        key: "campaign",
        label: "Кампания",
        field: "campaign"
    },
    {
        key: "group_name",
        label: "Группа",
        field: "group_name"
    },
    {
        key: "ad_name",
        label: "Объявление",
        field: "ad_name"
    },
    {
        key: "keyword",
        label: "Ключевая фраза",
        field: "keyword"
    },
    {
        key: "region",
        label: "Регион",
        field: "region"
    },
    {
        key: "device",
        label: "Устройство",
        field: "device"
    },
    {
        key: "placement",
        label: "Площадка",
        field: "placement"
    },
    {
        key: "position",
        label: "Position",
        field: "position"
    },
    {
        key: "url",
        label: "URL",
        field: "url"
    },
    {
        key: "product",
        label: "Продукт",
        field: "product"
    },
    {
        key: "graph",
        label: "Графики",
        field: null
    },
    {
        key: "plan",
        label: "План",
        field: null
    }
];
const FILTERS = [
    {
        key: "source",
        label: "Источник"
    },
    {
        key: "type",
        label: "Тип"
    },
    {
        key: "campaign",
        label: "Кампания"
    },
    {
        key: "group_name",
        label: "Группа"
    },
    {
        key: "ad_name",
        label: "Объявление"
    },
    {
        key: "keyword",
        label: "Ключевая фраза"
    },
    {
        key: "region",
        label: "Регион"
    },
    {
        key: "device",
        label: "Устройство"
    },
    {
        key: "placement",
        label: "Площадка"
    },
    {
        key: "position",
        label: "Position"
    },
    {
        key: "url",
        label: "URL"
    },
    {
        key: "product",
        label: "Продукт"
    }
];const ADS_CONNECTION_PLATFORMS = [
    {
        key: "yandex_direct",
        label: "Яндекс.Директ"
    },
    {
        key: "google_ads",
        label: "Google Ads"
    },
    {
        key: "vk_ads",
        label: "VK Ads"
    },
    {
        key: "telegram_ads",
        label: "Telegram Ads"
    }
];
const CRM_CONNECTION_PLATFORMS = [
    {
        key: "amocrm",
        label: "AmoCRM"
    },
    {
        key: "bitrix24",
        label: "Bitrix24"
    }
];
const GRAPH_METRICS = [
    {
        key: "cost",
        label: "Расход"
    },
    {
        key: "impressions",
        label: "Показы"
    },
    {
        key: "clicks",
        label: "Клики"
    },
    {
        key: "cpc",
        label: "CPC"
    },
    {
        key: "ctr",
        label: "CTR"
    },
    {
        key: "leads",
        label: "Лиды"
    },
    {
        key: "cpl",
        label: "CPL"
    },
    {
        key: "cr1",
        label: "CR1"
    },
    {
        key: "sales",
        label: "Продажи"
    },
    {
        key: "cr2",
        label: "CR2"
    },
    {
        key: "avg_check",
        label: "Ср.чек"
    },
    {
        key: "revenue",
        label: "Выручка"
    },
    {
        key: "margin",
        label: "Маржа"
    },
    {
        key: "romi",
        label: "ROMI"
    }
];
const GROUPINGS = [
    {
        key: "day",
        label: "день"
    },
    {
        key: "week",
        label: "неделя"
    },
    {
        key: "month",
        label: "месяц"
    },
    {
        key: "quarter",
        label: "квартал"
    },
    {
        key: "year",
        label: "год"
    }
];
const EXPORTABLE_TABS = TABS.filter((tab)=>tab.field);
function formatInt(value) {
    return "".concat(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}
function formatDecimal(value) {
    return value.toFixed(2).replace(".", ",");
}
function formatPercent(value) {
    return "".concat(formatDecimal(value), "%");
}
function parseDateLabel(value) {
    const [d, m, y] = value.split(".").map(Number);
    return new Date(y, (m !== null && m !== void 0 ? m : 1) - 1, d !== null && d !== void 0 ? d : 1).getTime();
}
function parseRecordDate(value) {
    const [d, m, y] = value.split(".").map(Number);
    return new Date(y, (m !== null && m !== void 0 ? m : 1) - 1, d !== null && d !== void 0 ? d : 1);
}
function toInputDate(value) {
    const [d, m, y] = value.split(".");
    return "".concat(y, "-").concat(m, "-").concat(d);
}
function fromInputDate(value) {
    return new Date("".concat(value, "T00:00:00")).getTime();
}
function formatDate(date) {
    return "".concat("".concat(date.getDate()).padStart(2, "0"), ".").concat("".concat(date.getMonth() + 1).padStart(2, "0"), ".").concat(date.getFullYear());
}
function formatDateTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Не определено";
    return "".concat(formatDate(date), " ").concat("".concat(date.getHours()).padStart(2, "0"), ":").concat("".concat(date.getMinutes()).padStart(2, "0"));
}
function getWeekStart(date) {
    const normalized = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const day = normalized.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    normalized.setDate(normalized.getDate() + diff);
    return normalized;
}
function getQuarter(date) {
    return Math.floor(date.getMonth() / 3) + 1;
}
function buildDateGroupLabel(date, grouping) {
    if (grouping === "day") return formatDate(date);
    if (grouping === "week") {
        const start = getWeekStart(date);
        const end = new Date(start);
        end.setDate(start.getDate() + 6);
        return "".concat(formatDate(start), " - ").concat(formatDate(end));
    }
    if (grouping === "month") return "".concat("".concat(date.getMonth() + 1).padStart(2, "0"), ".").concat(date.getFullYear());
    if (grouping === "quarter") return "Q".concat(getQuarter(date), " ").concat(date.getFullYear());
    return "".concat(date.getFullYear());
}
function buildDateGroupSortKey(date, grouping) {
    if (grouping === "day") return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    if (grouping === "week") return getWeekStart(date).getTime();
    if (grouping === "month") return new Date(date.getFullYear(), date.getMonth(), 1).getTime();
    if (grouping === "quarter") return new Date(date.getFullYear(), (getQuarter(date) - 1) * 3, 1).getTime();
    return new Date(date.getFullYear(), 0, 1).getTime();
}
function formatGraphAxisLabel(label, grouping) {
    if (grouping === "week" && label.includes(" - ")) {
        const parts = label.split(" - ");
        if (parts.length === 2) {
            const from = parts[0].slice(0, 5);
            const to = parts[1].slice(0, 5);
            return "".concat(from, "-").concat(to);
        }
    }
    return label;
}
function enumerateDates(from, to) {
    if (!from || !to) return [];
    const start = new Date("".concat(from, "T00:00:00"));
    const end = new Date("".concat(to, "T00:00:00"));
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];
    const dates = [];
    const cursor = new Date(start);
    while(cursor <= end){
        dates.push(new Date(cursor));
        cursor.setDate(cursor.getDate() + 1);
    }
    return dates;
}
function normalizePlanFilterValue(selected) {
    if (!selected || selected.length !== 1) return "Все";
    return selected[0] === "Не указано" ? "Все" : selected[0];
}
function normalizeFilterOptionValue(value) {
    const normalized = String(value ?? "").trim();
    if (!normalized) return "Не указано";
    const lower = normalized.toLowerCase();
    if (lower === "не указано" || lower === "(не указано)" || lower === "(не указано" || lower === "не указано)" || lower === "(?? ???????)".toLowerCase()) return "Не указано";
    return normalized;
}
function planMatchesFilters(plan, product, source, type) {
    const productMatches = product === "Все" || plan.product === product || plan.product === "Все";
    const sourceMatches = source === "Все" || plan.source === source || plan.source === "Все";
    const typeMatches = type === "Все" || plan.type === type || plan.type === "Все";
    return productMatches && sourceMatches && typeMatches;
}
function buildPlanTotals(plans, appliedDateFrom, appliedDateTo, product, source, type) {
    let costPlan = 0;
    let leadsPlan = 0;
    const selectedFrom = appliedDateFrom ? fromInputDate(appliedDateFrom) : Number.NEGATIVE_INFINITY;
    const selectedTo = appliedDateTo ? fromInputDate(appliedDateTo) : Number.POSITIVE_INFINITY;
    for (const plan of plans){
        if (!planMatchesFilters(plan, product, source, type)) continue;
        const planDays = enumerateDates(String(plan.period_from), String(plan.period_to));
        if (!planDays.length) continue;
        const dailyCost = Number(plan.budget || 0) / planDays.length;
        const dailyLeads = Number(plan.leads || 0) / planDays.length;
        for (const day of planDays){
            const dayTs = day.getTime();
            if (dayTs < selectedFrom || dayTs > selectedTo) continue;
            costPlan += dailyCost;
            leadsPlan += dailyLeads;
        }
    }
    return {
        costPlan,
        leadsPlan,
        cplPlan: leadsPlan > 0 ? costPlan / leadsPlan : 0
    };
}
function buildPlanMetrics(actualCost, actualLeads, actualCpl, costPlan, leadsPlan, cplPlan) {
    return {
        costPlan,
        leadsPlan,
        cplPlan,
        costPercent: costPlan > 0 ? actualCost / costPlan * 100 : null,
        leadsPercent: leadsPlan > 0 ? actualLeads / leadsPlan * 100 : null,
        cplPercent: cplPlan > 0 && actualCpl > 0 ? actualCpl / cplPlan * 100 : null
    };
}
function buildDatePlanMap(plans, grouping, appliedDateFrom, appliedDateTo, product, source, type) {
    const grouped = new Map();
    if (!plans.length) return grouped;
    const selectedFrom = appliedDateFrom ? fromInputDate(appliedDateFrom) : Number.NEGATIVE_INFINITY;
    const selectedTo = appliedDateTo ? fromInputDate(appliedDateTo) : Number.POSITIVE_INFINITY;
    for (const plan of plans){
        if (!planMatchesFilters(plan, product, source, type)) continue;
        const planDays = enumerateDates(String(plan.period_from), String(plan.period_to));
        if (!planDays.length) continue;
        const dailyCost = Number(plan.budget || 0) / planDays.length;
        const dailyLeads = Number(plan.leads || 0) / planDays.length;
        for (const day of planDays){
            const dayTs = day.getTime();
            if (dayTs < selectedFrom || dayTs > selectedTo) continue;
            const label = buildDateGroupLabel(day, grouping);
            var _grouped_get;
            const current = (_grouped_get = grouped.get(label)) !== null && _grouped_get !== void 0 ? _grouped_get : {
                costPlan: 0,
                leadsPlan: 0
            };
            current.costPlan += dailyCost;
            current.leadsPlan += dailyLeads;
            grouped.set(label, current);
        }
    }
    return grouped;
}
function buildKpiMetrics(records) {
    const totals = records.reduce((acc, record)=>({
            cost: acc.cost + record.cost,
            clicks: acc.clicks + record.clicks,
            impressions: acc.impressions + record.impressions,
            leads: acc.leads + record.leads,
            sales: acc.sales + record.sales,
            revenue: acc.revenue + record.revenue,
            margin: acc.margin + record.margin
        }), {
        cost: 0,
        clicks: 0,
        impressions: 0,
        leads: 0,
        sales: 0,
        revenue: 0,
        margin: 0
    });
    const cpc = totals.clicks > 0 ? totals.cost / totals.clicks : 0;
    const cpl = totals.leads > 0 ? totals.cost / totals.leads : 0;
    const cr1 = totals.clicks > 0 ? totals.leads / totals.clicks * 100 : 0;
    const cr2 = totals.leads > 0 ? totals.sales / totals.leads * 100 : 0;
    const avgCheck = totals.sales > 0 ? totals.revenue / totals.sales : 0;
    const romi = totals.cost > 0 ? totals.margin / totals.cost * 100 : -100;
    return [
        {
            label: "Расход",
            value: formatInt(totals.cost)
        },
        {
            label: "Клики",
            value: formatInt(totals.clicks)
        },
        {
            label: "CPC",
            value: formatInt(cpc)
        },
        {
            label: "Лиды",
            value: formatInt(totals.leads)
        },
        {
            label: "CPL",
            value: formatInt(cpl)
        },
        {
            label: "CR1",
            value: formatDecimal(cr1)
        },
        {
            label: "Продажи",
            value: formatInt(totals.sales)
        },
        {
            label: "CR2",
            value: formatDecimal(cr2)
        },
        {
            label: "Ср.чек",
            value: formatInt(avgCheck)
        },
        {
            label: "Выручка",
            value: formatInt(totals.revenue)
        },
        {
            label: "Маржа",
            value: formatInt(totals.margin)
        },
        {
            label: "ROMI",
            value: formatPercent(romi)
        }
    ];
}
function aggregateByDate(records, grouping, appliedDateFrom, appliedDateTo) {
    const grouped = new Map();
    for (const day of enumerateDates(appliedDateFrom, appliedDateTo)){
        const label = buildDateGroupLabel(day, grouping);
        const sortKey = buildDateGroupSortKey(day, grouping);
        if (!grouped.has(label)) {
            grouped.set(label, {
                label,
                sortKey,
                cost: 0,
                impressions: 0,
                clicks: 0,
                leads: 0,
                sales: 0,
                revenue: 0,
                margin: 0
            });
        }
    }
    for (const record of records){
        const date = parseRecordDate(record.date);
        const label = buildDateGroupLabel(date, grouping);
        const sortKey = buildDateGroupSortKey(date, grouping);
        var _grouped_get;
        const current = (_grouped_get = grouped.get(label)) !== null && _grouped_get !== void 0 ? _grouped_get : {
            label,
            sortKey,
            cost: 0,
            impressions: 0,
            clicks: 0,
            leads: 0,
            sales: 0,
            revenue: 0,
            margin: 0
        };
        current.cost += record.cost;
        current.impressions += record.impressions;
        current.clicks += record.clicks;
        current.leads += record.leads;
        current.sales += record.sales;
        current.revenue += record.revenue;
        current.margin += record.margin;
        grouped.set(label, current);
    }
    return Array.from(grouped.values()).sort((a, b)=>a.sortKey - b.sortKey).map((param)=>{
        let { sortKey: _sortKey, ...row } = param;
        return row;
    });
}
function buildTable(records, tab, grouping, plans, appliedDateFrom, appliedDateTo, product, source, type) {
    var _TABS_find;
    const tabDef = (_TABS_find = TABS.find((item)=>item.key === tab)) !== null && _TABS_find !== void 0 ? _TABS_find : TABS[0];
    const planTotals = buildPlanTotals(plans, appliedDateFrom, appliedDateTo, product, source, type);
    const datePlanMap = buildDatePlanMap(plans, grouping, appliedDateFrom, appliedDateTo, product, source, type);
    const rowsSource = tab === "date" ? aggregateByDate(records, grouping, appliedDateFrom, appliedDateTo) : (()=>{
        const grouped = new Map();
        for (const record of records){
            if (!tabDef.field) continue;
            var _record_tabDef_field;
            const label = String((_record_tabDef_field = record[tabDef.field]) !== null && _record_tabDef_field !== void 0 ? _record_tabDef_field : "Не указано");
            var _grouped_get;
            const current = (_grouped_get = grouped.get(label)) !== null && _grouped_get !== void 0 ? _grouped_get : {
                label,
                cost: 0,
                impressions: 0,
                clicks: 0,
                leads: 0,
                sales: 0,
                revenue: 0,
                margin: 0
            };
            current.cost += record.cost;
            current.impressions += record.impressions;
            current.clicks += record.clicks;
            current.leads += record.leads;
            current.sales += record.sales;
            current.revenue += record.revenue;
            current.margin += record.margin;
            grouped.set(label, current);
        }
        return Array.from(grouped.values()).sort((a, b)=>b.cost - a.cost);
    })();
    const rows = rowsSource.map((row)=>{
        const cpc = row.clicks > 0 ? row.cost / row.clicks : 0;
        const ctr = row.impressions > 0 ? row.clicks / row.impressions * 100 : 0;
        const cpl = row.leads > 0 ? row.cost / row.leads : 0;
        const cr1 = row.clicks > 0 ? row.leads / row.clicks * 100 : 0;
        const cr2 = row.leads > 0 ? row.sales / row.leads * 100 : 0;
        const avgCheck = row.sales > 0 ? row.revenue / row.sales : 0;
        const romi = row.cost > 0 ? row.margin / row.cost * 100 : -100;
        const rowPlan = tab === "date" ? (()=>{
            var _datePlanMap_get;
            const datePlan = (_datePlanMap_get = datePlanMap.get(row.label)) !== null && _datePlanMap_get !== void 0 ? _datePlanMap_get : {
                costPlan: 0,
                leadsPlan: 0
            };
            return buildPlanMetrics(row.cost, row.leads, cpl, datePlan.costPlan, datePlan.leadsPlan, datePlan.leadsPlan > 0 ? datePlan.costPlan / datePlan.leadsPlan : 0);
        })() : buildPlanMetrics(row.cost, row.leads, cpl, 0, 0, 0);
        const defaultValues = [
            row.label,
            formatInt(row.cost),
            formatInt(row.impressions),
            formatInt(row.clicks),
            formatInt(cpc),
            formatPercent(ctr),
            formatInt(row.leads),
            formatInt(cpl),
            formatPercent(cr1),
            formatInt(row.sales),
            formatPercent(cr2),
            formatInt(avgCheck),
            formatInt(row.revenue),
            formatInt(row.margin),
            formatPercent(romi)
        ];
        const dateValues = [
            row.label,
            formatInt(row.cost),
            rowPlan.costPlan > 0 ? formatInt(rowPlan.costPlan) : "—",
            rowPlan.costPercent !== null ? formatPercent(rowPlan.costPercent) : "—",
            formatInt(row.impressions),
            formatInt(row.clicks),
            formatInt(cpc),
            formatPercent(ctr),
            formatInt(row.leads),
            rowPlan.leadsPlan > 0 ? formatInt(rowPlan.leadsPlan) : "—",
            rowPlan.leadsPercent !== null ? formatPercent(rowPlan.leadsPercent) : "—",
            formatInt(cpl),
            rowPlan.cplPlan > 0 ? formatInt(rowPlan.cplPlan) : "—",
            rowPlan.cplPercent !== null ? formatPercent(rowPlan.cplPercent) : "—",
            formatPercent(cr1),
            formatInt(row.sales),
            formatPercent(cr2),
            formatInt(avgCheck),
            formatInt(row.revenue),
            formatInt(row.margin),
            formatPercent(romi)
        ];
        return {
            values: tab === "date" ? dateValues : defaultValues,
            isTotal: false
        };
    });
    const totals = buildKpiMetrics(records);
    const totalsMap = new Map(totals.map((item)=>[
            item.label,
            item.value
        ]));
    const totalClicks = records.reduce((sum, record)=>sum + record.clicks, 0);
    const totalImpressions = records.reduce((sum, record)=>sum + record.impressions, 0);
    const totalCost = records.reduce((sum, record)=>sum + record.cost, 0);
    const totalLeads = records.reduce((sum, record)=>sum + record.leads, 0);
    const totalCpl = totalLeads > 0 ? totalCost / totalLeads : 0;
    const totalPlan = buildPlanMetrics(totalCost, totalLeads, totalCpl, planTotals.costPlan, planTotals.leadsPlan, planTotals.cplPlan);
    var _totalsMap_get, _totalsMap_get1, _totalsMap_get2, _totalsMap_get3, _totalsMap_get4, _totalsMap_get5, _totalsMap_get6, _totalsMap_get7, _totalsMap_get8, _totalsMap_get9, _totalsMap_get10;
    const defaultTotalValues = [
        "ИТОГО",
        (_totalsMap_get = totalsMap.get("Расход")) !== null && _totalsMap_get !== void 0 ? _totalsMap_get : "0",
        formatInt(totalImpressions),
        (_totalsMap_get1 = totalsMap.get("Клики")) !== null && _totalsMap_get1 !== void 0 ? _totalsMap_get1 : "0",
        formatInt(totalClicks > 0 ? totalCost / totalClicks : 0),
        formatPercent(totalImpressions > 0 ? totalClicks / totalImpressions * 100 : 0),
        (_totalsMap_get2 = totalsMap.get("Лиды")) !== null && _totalsMap_get2 !== void 0 ? _totalsMap_get2 : "0",
        (_totalsMap_get3 = totalsMap.get("CPL")) !== null && _totalsMap_get3 !== void 0 ? _totalsMap_get3 : "0",
        "".concat((_totalsMap_get4 = totalsMap.get("CR1")) !== null && _totalsMap_get4 !== void 0 ? _totalsMap_get4 : "0", "%"),
        (_totalsMap_get5 = totalsMap.get("Продажи")) !== null && _totalsMap_get5 !== void 0 ? _totalsMap_get5 : "0",
        "".concat((_totalsMap_get6 = totalsMap.get("CR2")) !== null && _totalsMap_get6 !== void 0 ? _totalsMap_get6 : "0", "%"),
        (_totalsMap_get7 = totalsMap.get("Ср.чек")) !== null && _totalsMap_get7 !== void 0 ? _totalsMap_get7 : "0",
        (_totalsMap_get8 = totalsMap.get("Выручка")) !== null && _totalsMap_get8 !== void 0 ? _totalsMap_get8 : "0",
        (_totalsMap_get9 = totalsMap.get("Маржа")) !== null && _totalsMap_get9 !== void 0 ? _totalsMap_get9 : "0",
        (_totalsMap_get10 = totalsMap.get("ROMI")) !== null && _totalsMap_get10 !== void 0 ? _totalsMap_get10 : "-100,00%"
    ];
    var _totalsMap_get11, _totalsMap_get12, _totalsMap_get13, _totalsMap_get14, _totalsMap_get15, _totalsMap_get16, _totalsMap_get17, _totalsMap_get18, _totalsMap_get19, _totalsMap_get20, _totalsMap_get21;
    const dateTotalValues = [
        "ИТОГО",
        (_totalsMap_get11 = totalsMap.get("Расход")) !== null && _totalsMap_get11 !== void 0 ? _totalsMap_get11 : "0",
        totalPlan.costPlan > 0 ? formatInt(totalPlan.costPlan) : "0",
        totalPlan.costPercent !== null ? formatPercent(totalPlan.costPercent) : "0,00%",
        formatInt(totalImpressions),
        (_totalsMap_get12 = totalsMap.get("Клики")) !== null && _totalsMap_get12 !== void 0 ? _totalsMap_get12 : "0",
        formatInt(totalClicks > 0 ? totalCost / totalClicks : 0),
        formatPercent(totalImpressions > 0 ? totalClicks / totalImpressions * 100 : 0),
        (_totalsMap_get13 = totalsMap.get("Лиды")) !== null && _totalsMap_get13 !== void 0 ? _totalsMap_get13 : "0",
        totalPlan.leadsPlan > 0 ? formatInt(totalPlan.leadsPlan) : "0",
        totalPlan.leadsPercent !== null ? formatPercent(totalPlan.leadsPercent) : "0,00%",
        (_totalsMap_get14 = totalsMap.get("CPL")) !== null && _totalsMap_get14 !== void 0 ? _totalsMap_get14 : "0",
        totalPlan.cplPlan > 0 ? formatInt(totalPlan.cplPlan) : "0",
        totalPlan.cplPercent !== null ? formatPercent(totalPlan.cplPercent) : "0,00%",
        "".concat((_totalsMap_get15 = totalsMap.get("CR1")) !== null && _totalsMap_get15 !== void 0 ? _totalsMap_get15 : "0", "%"),
        (_totalsMap_get16 = totalsMap.get("Продажи")) !== null && _totalsMap_get16 !== void 0 ? _totalsMap_get16 : "0",
        "".concat((_totalsMap_get17 = totalsMap.get("CR2")) !== null && _totalsMap_get17 !== void 0 ? _totalsMap_get17 : "0", "%"),
        (_totalsMap_get18 = totalsMap.get("Ср.чек")) !== null && _totalsMap_get18 !== void 0 ? _totalsMap_get18 : "0",
        (_totalsMap_get19 = totalsMap.get("Выручка")) !== null && _totalsMap_get19 !== void 0 ? _totalsMap_get19 : "0",
        (_totalsMap_get20 = totalsMap.get("Маржа")) !== null && _totalsMap_get20 !== void 0 ? _totalsMap_get20 : "0",
        (_totalsMap_get21 = totalsMap.get("ROMI")) !== null && _totalsMap_get21 !== void 0 ? _totalsMap_get21 : "-100,00%"
    ];
    rows.push({
        values: tab === "date" ? dateTotalValues : defaultTotalValues,
        isTotal: true
    });
    const defaultHeaders = [
        tabDef.label,
        "Расход",
        "Показы",
        "Клики",
        "CPC",
        "CTR",
        "Лиды",
        "CPL",
        "CR1",
        "Продажи",
        "CR2",
        "Ср.чек",
        "Выручка",
        "Маржа",
        "ROMI"
    ];
    const dateHeaders = [
        tabDef.label,
        "Расход",
        "Расход план",
        "Расход %",
        "Показы",
        "Клики",
        "CPC",
        "CTR",
        "Лиды",
        "Лиды план",
        "Лиды %",
        "CPL",
        "CPL план",
        "CPL %",
        "CR1",
        "Продажи",
        "CR2",
        "Ср.чек",
        "Выручка",
        "Маржа",
        "ROMI"
    ];
    return {
        headers: tab === "date" ? dateHeaders : defaultHeaders,
        rows
    };
}
function getGraphMetricValue(row, metric) {
    const cpc = row.clicks > 0 ? row.cost / row.clicks : 0;
    const ctr = row.impressions > 0 ? row.clicks / row.impressions * 100 : 0;
    const cpl = row.leads > 0 ? row.cost / row.leads : 0;
    const cr1 = row.clicks > 0 ? row.leads / row.clicks * 100 : 0;
    const cr2 = row.leads > 0 ? row.sales / row.leads * 100 : 0;
    const avgCheck = row.sales > 0 ? row.revenue / row.sales : 0;
    const romi = row.cost > 0 ? row.margin / row.cost * 100 : -100;
    switch(metric){
        case "impressions":
            return row.impressions;
        case "clicks":
            return row.clicks;
        case "cpc":
            return cpc;
        case "ctr":
            return ctr;
        case "leads":
            return row.leads;
        case "cpl":
            return cpl;
        case "cr1":
            return cr1;
        case "sales":
            return row.sales;
        case "cr2":
            return cr2;
        case "avg_check":
            return avgCheck;
        case "revenue":
            return row.revenue;
        case "margin":
            return row.margin;
        case "romi":
            return romi;
        default:
            return row.cost;
    }
}
function formatGraphMetricValue(metric, value) {
    if ([
        "ctr",
        "cr1",
        "cr2",
        "romi"
    ].includes(metric)) return formatPercent(value);
    return formatInt(value);
}
function buildGraphRows(records, metric, grouping, appliedDateFrom, appliedDateTo) {
    return aggregateByDate(records, grouping, appliedDateFrom, appliedDateTo).map((row)=>({
            label: row.label,
            value: getGraphMetricValue(row, metric)
        }));
}
function parseSortableNumeric(value) {
    const normalized = value.replace(/\s/g, "").replace(/%/g, "").replace(/,/g, ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
}
function getPlanCellClass(header, value) {
    const percentHeaders = new Set([
        "Расход %",
        "Лиды %",
        "CPL %"
    ]);
    if (value === "—") return percentHeaders.has(header) ? "cell-plan-muted" : "";
    const numericValue = parseSortableNumeric(value);
    if (!Number.isFinite(numericValue)) return "";
    if (header === "ROMI") {
        if (numericValue > 50) return "cell-romi-strong-good";
        if (numericValue > 10) return "cell-romi-good";
        if (numericValue < -50) return "cell-romi-strong-bad";
        if (numericValue < -10) return "cell-romi-bad";
        return "";
    }
    if (numericValue <= 0) return percentHeaders.has(header) ? "cell-plan-muted" : "";
    if (header === "Расход %") {
        return numericValue <= 100 ? "cell-plan-good" : "cell-plan-bad";
    }
    if (header === "Лиды %") {
        return numericValue >= 100 ? "cell-plan-good" : "cell-plan-bad";
    }
    if (header === "CPL %") {
        return numericValue <= 100 ? "cell-plan-good" : "cell-plan-bad";
    }
    return "";
}
function parseSortableDateLabel(value, grouping) {
    if (grouping === "day") return parseDateLabel(value);
    var _value_split_;
    if (grouping === "week") return parseDateLabel((_value_split_ = value.split(" - ")[0]) !== null && _value_split_ !== void 0 ? _value_split_ : value);
    if (grouping === "month") {
        const [month, year] = value.split(".").map(Number);
        return new Date(year || 1970, (month || 1) - 1, 1).getTime();
    }
    if (grouping === "quarter") {
        const match = value.match(/^Q(\d)\s+(\d{4})$/);
        if (match) return new Date(Number(match[2]), (Number(match[1]) - 1) * 3, 1).getTime();
    }
    return new Date(Number(value) || 1970, 0, 1).getTime();
}
function sortTableRows(rows, sortState, tab, grouping) {
    if (!sortState) return rows;
    const dataRows = rows.filter((row)=>!row.isTotal);
    var _rows_find;
    const totalRow = (_rows_find = rows.find((row)=>row.isTotal)) !== null && _rows_find !== void 0 ? _rows_find : null;
    const factor = sortState.direction === "asc" ? 1 : -1;
    dataRows.sort((left, right)=>{
        var _left_values_sortState_columnIndex;
        const leftValue = (_left_values_sortState_columnIndex = left.values[sortState.columnIndex]) !== null && _left_values_sortState_columnIndex !== void 0 ? _left_values_sortState_columnIndex : "";
        var _right_values_sortState_columnIndex;
        const rightValue = (_right_values_sortState_columnIndex = right.values[sortState.columnIndex]) !== null && _right_values_sortState_columnIndex !== void 0 ? _right_values_sortState_columnIndex : "";
        if (sortState.columnIndex === 0) {
            if (tab === "date") {
                return (parseSortableDateLabel(leftValue, grouping) - parseSortableDateLabel(rightValue, grouping)) * factor;
            }
            return leftValue.localeCompare(rightValue, "ru") * factor;
        }
        return (parseSortableNumeric(leftValue) - parseSortableNumeric(rightValue)) * factor;
    });
    return totalRow ? [
        ...dataRows,
        totalRow
    ] : dataRows;
}
function decodeByteString(value, encoding) {
    return new TextDecoder(encoding).decode(Uint8Array.from(Array.from(value).map((char)=>char.charCodeAt(0) & 0xff)));
}
function scoreReadableText(value) {
    var _value_match;
    const cyrillic = ((_value_match = value.match(/[А-Яа-яЁё]/g)) !== null && _value_match !== void 0 ? _value_match : []).length;
    var _value_match1;
    const latin = ((_value_match1 = value.match(/[A-Za-z]/g)) !== null && _value_match1 !== void 0 ? _value_match1 : []).length;
    var _value_match2;
    const digits = ((_value_match2 = value.match(/[0-9]/g)) !== null && _value_match2 !== void 0 ? _value_match2 : []).length;
    var _value_match3;
    const spaces = ((_value_match3 = value.match(/[\s.,:;()\-]/g)) !== null && _value_match3 !== void 0 ? _value_match3 : []).length;
    var _value_match4;
    const mojibake = ((_value_match4 = value.match(/[ÐÑÃÍ�]/g)) !== null && _value_match4 !== void 0 ? _value_match4 : []).length;
    return cyrillic * 4 + latin + digits + spaces - mojibake * 3;
}
function repairText(value) {
    const text = String(value !== null && value !== void 0 ? value : "").trim();
    if (!text) return "";
    const looksHealthyCyrillic = /[А-Яа-яЁё]/.test(text) && !/[ÐÑÃÍÂ]/.test(text);
    if (looksHealthyCyrillic) return text;
    const looksMojibake = /[ÐÑÃÍÂÊËÎÓ]/.test(text) || /Р.|С./.test(text);
    if (!looksMojibake) return text;
    const candidates = new Set([
        text
    ]);
    try {
        candidates.add(decodeByteString(text, "utf-8"));
    } catch (e) {}
    try {
        candidates.add(decodeByteString(text, "windows-1251"));
    } catch (e) {}
    var _Array_from_sort_;
    return (_Array_from_sort_ = Array.from(candidates).sort((left, right)=>scoreReadableText(right) - scoreReadableText(left))[0]) !== null && _Array_from_sort_ !== void 0 ? _Array_from_sort_ : text;
}
function getRecordText(record, key) {
    var _record_key;
    return repairText((_record_key = record[key]) !== null && _record_key !== void 0 ? _record_key : "\u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u043e") || "\u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u043e";
}
function normalizeHeader(value) {
    return repairText(value).toLowerCase().replace(/\u0451/g, "\u0435").replace(/[^a-z\u0430-\u044f0-9]/g, "");
}
function getCell(row, aliases) {
    const aliasSet = new Set(aliases.map(normalizeHeader));
    for (const [key, value] of Object.entries(row)){
        if (aliasSet.has(normalizeHeader(key))) return value;
    }
    return undefined;
}
function toNumber(value) {
    if (typeof value === "number") return value;
    const normalized = repairText(value !== null && value !== void 0 ? value : "").replace(/\s/g, "").replace(/,/g, ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
}
function parseDateValue(value) {
    if (value instanceof Date && !Number.isNaN(value.getTime())) return formatDate(value);
    if (typeof value === "number") {
        const date = XLSX.SSF.parse_date_code(value);
        if (date) return formatDate(new Date(date.y, date.m - 1, date.d));
    }
    const text = repairText(value).trim();
    if (!text) return "";
    if (/^\d{4}-\d{2}-\d{2}/.test(text)) return formatDate(new Date("".concat(text.slice(0, 10), "T00:00:00")));
    if (/^\d{2}\.\d{2}\.\d{2,4}$/.test(text)) {
        const [d, m, y0] = text.split(".");
        const y = y0.length === 2 ? "20".concat(y0) : y0;
        return "".concat(d, ".").concat(m, ".").concat(y);
    }
    return text;
}
function hasMojibakeHeaders(rows) {
    var _rows_;
    const keys = Object.keys((_rows_ = rows[0]) !== null && _rows_ !== void 0 ? _rows_ : {});
    return keys.some((key)=>/Р.|С./.test(key));
}
function splitDelimitedLine(line, delimiter) {
    const result = [];
    let current = "";
    let inQuotes = false;
    for(let index = 0; index < line.length; index += 1){
        const char = line[index];
        const next = line[index + 1];
        if (char === '"') {
            if (inQuotes && next === '"') {
                current += '"';
                index += 1;
            } else {
                inQuotes = !inQuotes;
            }
            continue;
        }
        if (char === delimiter && !inQuotes) {
            result.push(current);
            current = "";
            continue;
        }
        current += char;
    }
    result.push(current);
    return result.map((value)=>value.trim());
}
function parseCsvText(text) {
    var _lines__match, _lines__match1;
    const normalized = text.replace(/^\ufeff/, "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const lines = normalized.split("\n").filter((line)=>line.trim().length > 0);
    if (lines.length === 0) return [];
    var _lines__match_length, _lines__match_length1;
    const delimiter = ((_lines__match_length = (_lines__match = lines[0].match(/;/g)) === null || _lines__match === void 0 ? void 0 : _lines__match.length) !== null && _lines__match_length !== void 0 ? _lines__match_length : 0) > ((_lines__match_length1 = (_lines__match1 = lines[0].match(/,/g)) === null || _lines__match1 === void 0 ? void 0 : _lines__match1.length) !== null && _lines__match_length1 !== void 0 ? _lines__match_length1 : 0) ? ";" : ",";
    const headers = splitDelimitedLine(lines[0], delimiter);
    return lines.slice(1).map((line)=>{
        const values = splitDelimitedLine(line, delimiter);
        return headers.reduce((accumulator, header, index)=>{
            var _values_index;
            accumulator[header] = (_values_index = values[index]) !== null && _values_index !== void 0 ? _values_index : "";
            return accumulator;
        }, {});
    });
}
async function readStructuredRows(file) {
    var _file_name_split_pop;
    const ext = (_file_name_split_pop = file.name.split(".").pop()) === null || _file_name_split_pop === void 0 ? void 0 : _file_name_split_pop.toLowerCase();
    if (ext === "json") {
        const parsed = JSON.parse(await file.text());
        if (!Array.isArray(parsed)) throw new Error("JSON должен содержать массив строк");
        return parsed;
    }
    const buffer = await file.arrayBuffer();
    if (ext === "csv") {
        const utf8Text = new TextDecoder("utf-8").decode(buffer);
        let rows = parseCsvText(utf8Text);
        if (!rows.length || hasMojibakeHeaders(rows)) {
            const cp1251Text = new TextDecoder("windows-1251").decode(buffer);
            rows = parseCsvText(cp1251Text);
        }
        return rows;
    }
    const workbook = XLSX.read(buffer, {
        type: "array"
    });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    return XLSX.utils.sheet_to_json(sheet, {
        defval: ""
    });
}
function mapAdsRow(row) {
    const date = parseDateValue(getCell(row, [
        "Все?",
        "date",
        "Все?"
    ]));
    if (!date) return null;
    var _getCell, _getCell1, _getCell2, _getCell3, _getCell4, _getCell5;
    return {
        date,
        source: String((_getCell = getCell(row, [
            "Ничего??",
            "source",
            "НичегоВсе?"
        ])) !== null && _getCell !== void 0 ? _getCell : "Не указано"),
        medium: String((_getCell1 = getCell(row, [
            "Все",
            "medium",
            "Все?"
        ])) !== null && _getCell1 !== void 0 ? _getCell1 : "Не указано"),
        campaign: String((_getCell2 = getCell(row, [
            "Ничего??",
            "campaign"
        ])) !== null && _getCell2 !== void 0 ? _getCell2 : "(Не указано)"),
        group_name: String((_getCell3 = getCell(row, [
            "Ничего",
            "group",
            "groupname",
            "gbid"
        ])) !== null && _getCell3 !== void 0 ? _getCell3 : "(Не указано)"),
        ad_name: String((_getCell4 = getCell(row, [
            "НичегоВсе?",
            "ad",
            "adname",
            "content"
        ])) !== null && _getCell4 !== void 0 ? _getCell4 : "(Не указано)"),
        keyword: String((_getCell5 = getCell(row, [
            "НичегоНичего?",
            "keyword",
            "term"
        ])) !== null && _getCell5 !== void 0 ? _getCell5 : "(Не указано)"),
        region: String(getCell(row, ["Ничего", "region", "regionname", "region_name", "{region_name}"]) ?? "(Не указано)"),
        device: String(getCell(row, ["НичегоВсе?", "device", "devicetype", "device_type", "{device_type}"]) ?? "(Не указано)"),
        placement: String(getCell(row, ["Ничего??", "placement", "site", "source", "{source}"]) ?? "(Не указано)"),
        position: String(getCell(row, ["position", "Ничего?", "{position}"]) ?? "(Не указано)"),
        url: String(getCell(row, ["url", "Ничего", "link", "finalurl"]) ?? "(Не указано)"),
        product: String(getCell(row, ["Ничего?", "product", "sku", "item"]) ?? "(Не указано)"),
        cost: toNumber(getCell(row, ["Ничего", "cost", "spend"])),
        impressions: Math.round(toNumber(getCell(row, ["Ничего", "impressions"]))),
        clicks: Math.round(toNumber(getCell(row, ["Все??", "clicks"])))
    };
}
function mapCrmRow(row) {
    const date = parseDateValue(getCell(row, [
        "Все?",
        "date",
        "Все?"
    ]));
    if (!date) return null;
    var _getCell, _getCell1, _getCell2, _getCell3, _getCell4, _getCell5;
    return {
        date,
        source: String((_getCell = getCell(row, ["Ничего??", "source", "utm_source"])) !== null && _getCell !== void 0 ? _getCell : "Не указано"),
        medium: String((_getCell1 = getCell(row, ["Все", "medium", "utm_medium"])) !== null && _getCell1 !== void 0 ? _getCell1 : "Не указано"),
        campaign: String((_getCell2 = getCell(row, ["Ничего??", "campaign", "utm_campaign", "campaign_id", "{{campaign_id}}"])) !== null && _getCell2 !== void 0 ? _getCell2 : "(Не указано)"),
        group_name: String((_getCell3 = getCell(row, ["Ничего", "group", "groupname", "gbid", "{gbid}"])) !== null && _getCell3 !== void 0 ? _getCell3 : "(Не указано)"),
        ad_name: String((_getCell4 = getCell(row, ["НичегоВсе?", "ad", "adname", "content", "ad_id", "{ad_id}"])) !== null && _getCell4 !== void 0 ? _getCell4 : "(Не указано)"),
        keyword: String((_getCell5 = getCell(row, ["НичегоНичего?", "keyword", "term"])) !== null && _getCell5 !== void 0 ? _getCell5 : "(Не указано)"),
        region: String(getCell(row, ["Ничего", "region", "regionname", "region_name", "{region_name}"]) ?? "(Не указано)"),
        device: String(getCell(row, ["НичегоВсе?", "device", "devicetype", "device_type", "{device_type}"]) ?? "(Не указано)"),
        placement: String(getCell(row, ["Ничего??", "placement", "site", "source", "{source}"]) ?? "(Не указано)"),
        position: String(getCell(row, ["position", "Ничего?", "{position}"]) ?? "(Не указано)"),
        url: String(getCell(row, ["url", "Ничего", "link", "finalurl"]) ?? "(Не указано)"),
        product: String(getCell(row, ["Ничего?", "product", "sku", "item"]) ?? "(Не указано)"),
        leads: Math.round(toNumber(getCell(row, ["Все?", "leads"]))),
        sales: Math.round(toNumber(getCell(row, ["Ничего?", "sales"]))),
        revenue: toNumber(getCell(row, ["Ничего?", "revenue", "amount"]))
    };
}
function buildInitialFilterState(records) {
    const state = Object.fromEntries(FILTERS.map((filter)=>[
            filter.key,
            []
        ]));
    for (const filter of FILTERS){
        state[filter.key] = Array.from(new Set(records.map((record)=>{
            var _record_filter_key;
            return normalizeFilterOptionValue((_record_filter_key = record[filter.key]) !== null && _record_filter_key !== void 0 ? _record_filter_key : "Не указано");
        }).filter(Boolean))).sort((a, b)=>a.localeCompare(b, "ru"));
    }
    return state;
}
function buildInitialSearchState() {
    return Object.fromEntries(FILTERS.map((filter)=>[
            filter.key,
            ""
        ]));
}
function buildInitialOpenState() {
    return Object.fromEntries(FILTERS.map((filter)=>[
            filter.key,
            false
        ]));
}
function findCurrentPlan(plans, dateFrom, dateTo, planProduct, planSource, planType) {
    if (!dateFrom || !dateTo) return null;
    var _plans_find, _ref;
    return (_ref = (_plans_find = plans.find((plan)=>plan.period_from === dateFrom && plan.period_to === dateTo && plan.product === planProduct && plan.source === planSource && plan.type === planType)) !== null && _plans_find !== void 0 ? _plans_find : plans.find((plan)=>plan.period_from <= dateFrom && plan.period_to >= dateTo && planMatchesFilters(plan, planProduct, planSource, planType))) !== null && _ref !== void 0 ? _ref : null;
}
export default function ProjectDetailPage() {
    const params = useParams();
    const router = useRouter();
    const [dashboard, setDashboard] = useState(null);
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState("date");
    const [grouping, setGrouping] = useState("day");
    const [graphMetric, setGraphMetric] = useState("cost");
    const [graphGrouping, setGraphGrouping] = useState("day");
    const [filterState, setFilterState] = useState(buildInitialFilterState([]));
    const [filterSearch, setFilterSearch] = useState(buildInitialSearchState());
    const [filterOpen, setFilterOpen] = useState(buildInitialOpenState());
    const [draftDateFrom, setDraftDateFrom] = useState("");
    const [draftDateTo, setDraftDateTo] = useState("");
    const [appliedDateFrom, setAppliedDateFrom] = useState("");
    const [appliedDateTo, setAppliedDateTo] = useState("");
    const [planPeriodFrom, setPlanPeriodFrom] = useState("");
    const [planPeriodTo, setPlanPeriodTo] = useState("");
    const [planProduct, setPlanProduct] = useState("Все");
    const [planSource, setPlanSource] = useState("Все");
    const [planType, setPlanType] = useState("Все");
    const [planBudget, setPlanBudget] = useState("");
    const [planLeads, setPlanLeads] = useState("");
    const [planLoading, setPlanLoading] = useState(false);
    const [planMessage, setPlanMessage] = useState(null);
    const [loaderOpen, setLoaderOpen] = useState(false);
    const [connectionsOpen, setConnectionsOpen] = useState(false);
    const [connectionCategory, setConnectionCategory] = useState("ads");
    const [connections, setConnections] = useState([]);
    const [connectionsLoading, setConnectionsLoading] = useState(false);
    const [members, setMembers] = useState([]);
    const [membersLoading, setMembersLoading] = useState(false);
    const [connectionSaving, setConnectionSaving] = useState(false);
    const [connectionTestingId, setConnectionTestingId] = useState(null);
    const [editingConnectionId, setEditingConnectionId] = useState(null);
    const [connectionForm, setConnectionForm] = useState({
        category: "ads",
        platform: "yandex_direct",
        name: "",
        identifier: "",
        api_mode: "production",
        client_login_mode: "auto",
        token: "",
        client_id: "",
        client_secret: "",
        refresh_token: ""
    });
    const [adsRows, setAdsRows] = useState([]);
    const [crmRows, setCrmRows] = useState([]);
    const [adsRawRows, setAdsRawRows] = useState([]);
    const [crmRawRows, setCrmRawRows] = useState([]);
    const [adsColumns, setAdsColumns] = useState([]);
    const [crmColumns, setCrmColumns] = useState([]);
    const [adsMapping, setAdsMapping] = useState({});
    const [crmMapping, setCrmMapping] = useState({});
    const [adsFileName, setAdsFileName] = useState(null);
    const [crmFileName, setCrmFileName] = useState(null);
    const [replaceExisting, setReplaceExisting] = useState(true);
    const [importing, setImporting] = useState(false);
    const [tableSort, setTableSort] = useState(null);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [importMessage, setImportMessage] = useState(null);
    const adsInputRef = useRef(null);
    const crmInputRef = useRef(null);
    const currentUser = useMemo(()=>getStoredUser(), []);
    const isClientUser = (currentUser === null || currentUser === void 0 ? void 0 : currentUser.role) === "client";
    const canManageProjectWorkspace = !isClientUser;
    const canManageProjectAccess = (currentUser === null || currentUser === void 0 ? void 0 : currentUser.role) === "admin";
    async function loadConnections() {
        let silent = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : false;
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        try {
            if (!silent) setConnectionsLoading(true);
            const result = await fetchProjectConnections(token, params.projectId, "ads");
            setConnections(result);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Не удалось загрузить подключения";
            setError(message);
        } finally{
            if (!silent) setConnectionsLoading(false);
        }
    }
    async function loadMembers() {
        let silent = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : false;
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        try {
            if (!silent) setMembersLoading(true);
            const result = await fetchProjectMembers(token, params.projectId);
            setMembers(result);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Не удалось загрузить доступы проекта";
            setError(message);
        } finally {
            if (!silent) setMembersLoading(false);
        }
    }
    function resetConnectionForm() {
        let category = arguments.length > 0 && arguments[0] !== void 0 ? arguments[0] : connectionCategory;
        setEditingConnectionId(null);
        setConnectionCategory(category);
        setConnectionForm({
            category,
            platform: category === "crm" ? "amocrm" : "yandex_direct",
            name: "",
            identifier: "",
            api_mode: "production",
            client_login_mode: "auto",
            token: "",
            client_id: "",
            client_secret: "",
            refresh_token: ""
        });
    }
    function editConnection(connection) {
        setEditingConnectionId(connection.id);
        setConnectionForm({
            category: connection.category,
            platform: connection.platform,
            name: connection.name,
            identifier: connection.identifier,
            api_mode: connection.api_mode,
            client_login_mode: connection.client_login_mode,
            token: connection.token,
            client_id: connection.client_id,
            client_secret: connection.client_secret,
            refresh_token: connection.refresh_token
        });
        setConnectionsOpen(true);
    }
    async function handleSaveConnection() {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        const category = connectionForm.category === "crm" ? "crm" : "ads";
        var _connectionForm_name;
        const normalizedName = ((_connectionForm_name = connectionForm.name) !== null && _connectionForm_name !== void 0 ? _connectionForm_name : "").trim();
        var _connectionForm_identifier;
        const normalizedIdentifier = ((_connectionForm_identifier = connectionForm.identifier) !== null && _connectionForm_identifier !== void 0 ? _connectionForm_identifier : "").trim();
        var _connectionForm_token;
        const normalizedToken = ((_connectionForm_token = connectionForm.token) !== null && _connectionForm_token !== void 0 ? _connectionForm_token : "").trim();
        var _connectionForm_client_id;
        const normalizedClientId = ((_connectionForm_client_id = connectionForm.client_id) !== null && _connectionForm_client_id !== void 0 ? _connectionForm_client_id : "").trim();
        var _connectionForm_client_secret;
        const normalizedClientSecret = ((_connectionForm_client_secret = connectionForm.client_secret) !== null && _connectionForm_client_secret !== void 0 ? _connectionForm_client_secret : "").trim();
        var _connectionForm_platform;
        const platform = (_connectionForm_platform = connectionForm.platform) !== null && _connectionForm_platform !== void 0 ? _connectionForm_platform : category === "crm" ? "amocrm" : "yandex_direct";
        var _connectionForm_client_login_mode;
        const clientLoginMode = (_connectionForm_client_login_mode = connectionForm.client_login_mode) !== null && _connectionForm_client_login_mode !== void 0 ? _connectionForm_client_login_mode : "auto";
        if (!normalizedName) {
            setError("Заполните поле Название.");
            return;
        }
        if (category === "ads") {
            if ([
                "yandex_direct",
                "vk_ads",
                "telegram_ads"
            ].includes(platform) && !normalizedToken) {
                setError("Заполните поле Токен.");
                return;
            }
            if (platform === "google_ads" && (!normalizedClientId || !normalizedClientSecret)) {
                setError("Для Google Ads заполните Client ID и Client Secret.");
                return;
            }
            if (platform === "yandex_direct" && clientLoginMode === "always" && !normalizedIdentifier) {
                setError("Для режима 'Всегда использовать' заполните поле ID / логин.");
                return;
            }
        }
        if (category === "crm") {
            if (platform === "amocrm" && !normalizedToken) {
                setError("Для AmoCRM заполните поле Токен.");
                return;
            }
            if (platform === "bitrix24" && !normalizedIdentifier && !normalizedToken) {
                setError("Для Bitrix24 заполните портал или webhook / токен.");
                return;
            }
        }
        try {
            setConnectionSaving(true);
            setError(null);
            var _connectionForm_refresh_token;
            const payload = {
                ...connectionForm,
                category,
                platform,
                name: normalizedName,
                identifier: normalizedIdentifier,
                token: normalizedToken,
                client_id: normalizedClientId,
                client_secret: normalizedClientSecret,
                refresh_token: ((_connectionForm_refresh_token = connectionForm.refresh_token) !== null && _connectionForm_refresh_token !== void 0 ? _connectionForm_refresh_token : "").trim()
            };
            const saved = await saveProjectConnection(token, params.projectId, payload, editingConnectionId !== null && editingConnectionId !== void 0 ? editingConnectionId : undefined);
            setConnections((current)=>{
                const rest = current.filter((item)=>item.id !== saved.id);
                return [
                    saved,
                    ...rest
                ].sort((a, b)=>b.updated_at.localeCompare(a.updated_at));
            });
            resetConnectionForm(category);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось сохранить подключение");
        } finally{
            setConnectionSaving(false);
        }
    }
    async function handleTestConnection(connectionId) {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        try {
            setConnectionTestingId(connectionId);
            setError(null);
            const result = await testProjectConnection(token, params.projectId, connectionId);
            await loadConnections(true);
            setError(result.ok ? null : result.status_comment);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось проверить подключение");
        } finally{
            setConnectionTestingId(null);
        }
    }
    async function handleDeleteConnection(connectionId) {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        if (!window.confirm("Удалить это подключение?")) return;
        try {
            setError(null);
            await deleteProjectConnection(token, params.projectId, connectionId);
            setConnections((current)=>current.filter((item)=>item.id !== connectionId));
            if (editingConnectionId === connectionId) resetConnectionForm();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось удалить подключение");
        }
    }
    async function loadProject() {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        try {
            setError(null);
            const dashboardResult = await fetchProjectDashboard(token, params.projectId);
            setDashboard(dashboardResult);
            try {
                setPlans(await fetchProjectPlans(token, params.projectId));
            } catch (e) {
                setPlans([]);
            }
            try {
                await loadConnections(true);
            } catch (e) {
                setConnections([]);
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : "Не удалось загрузить проект";
            setError(message);
            if (message.includes("Сессия истекла")) router.replace("/login");
        } finally{
            setLoading(false);
        }
    }
    useEffect(()=>{
        if (params.projectId) void loadProject();
    }, [
        params.projectId
    ]);
    useEffect(()=>{
        if (!dashboard) return;
        var _dashboard_records;
        const records = (_dashboard_records = dashboard.records) !== null && _dashboard_records !== void 0 ? _dashboard_records : [];
        if (records.length > 0) {
            const sortedDates = records.map((record)=>record.date).sort((a, b)=>parseDateLabel(a) - parseDateLabel(b));
            const from = toInputDate(sortedDates[0]);
            const to = toInputDate(sortedDates[sortedDates.length - 1]);
            setDraftDateFrom(from);
            setDraftDateTo(to);
            setAppliedDateFrom(from);
            setAppliedDateTo(to);
            setPlanPeriodFrom(from);
            setPlanPeriodTo(to);
            const nextFilterState = buildInitialFilterState(records);
            for (const filter of FILTERS){
                if (!nextFilterState[filter.key].includes("Не указано")) {
                    nextFilterState[filter.key] = ["Не указано", ...nextFilterState[filter.key]];
                }
            }
            setFilterState(nextFilterState);
        }
    }, [
        dashboard === null || dashboard === void 0 ? void 0 : dashboard.project.id
    ]);
    const filterOptions = useMemo(()=>{
        var _dashboard_records;
        const records = (_dashboard_records = dashboard === null || dashboard === void 0 ? void 0 : dashboard.records) !== null && _dashboard_records !== void 0 ? _dashboard_records : [];
        const result = Object.fromEntries(FILTERS.map((filter)=>[
                filter.key,
                []
            ]));
        for (const filter of FILTERS){
            const options = Array.from(new Set(records.map((record)=>{
                var _record_filter_key;
                return normalizeFilterOptionValue((_record_filter_key = record[filter.key]) !== null && _record_filter_key !== void 0 ? _record_filter_key : "Не указано");
            }).filter(Boolean))).sort((a, b)=>a.localeCompare(b, "ru"));
            if (!options.includes("Не указано")) {
                options.unshift("Не указано");
            }
            result[filter.key] = options;
        }
        return result;
    }, [
        dashboard
    ]);
    const filteredRecords = useMemo(()=>{
        var _dashboard_records;
        const records = (_dashboard_records = dashboard === null || dashboard === void 0 ? void 0 : dashboard.records) !== null && _dashboard_records !== void 0 ? _dashboard_records : [];
        return records.filter((record)=>{
            const recordTime = parseDateLabel(record.date);
            if (appliedDateFrom && recordTime < fromInputDate(appliedDateFrom)) return false;
            if (appliedDateTo && recordTime > fromInputDate(appliedDateTo)) return false;
            return FILTERS.every((filter)=>{
                const selected = filterState[filter.key];
                const totalOptions = filterOptions[filter.key];
                const selectedSet = new Set(selected.filter((option)=>totalOptions.includes(option)));
                if (!totalOptions.length) return true;
                if (!selectedSet.size) return false;
                if (selectedSet.size === totalOptions.length) return true;
                return selectedSet.has(getRecordText(record, filter.key));
            });
        });
    }, [
        dashboard,
        appliedDateFrom,
        appliedDateTo,
        filterState,
        filterOptions
    ]);
    const kpiCards = useMemo(()=>buildKpiMetrics(filteredRecords), [
        filteredRecords
    ]);
    const activePlanProduct = useMemo(()=>{
        const selected = filterState.product;
        return normalizePlanFilterValue(selected);
    }, [
        filterState.product
    ]);
    const activePlanSource = useMemo(()=>{
        const selected = filterState.source;
        return normalizePlanFilterValue(selected);
    }, [
        filterState.source
    ]);
    const activePlanType = useMemo(()=>{
        const selected = filterState.type;
        return normalizePlanFilterValue(selected);
    }, [
        filterState.type
    ]);
    const currentPlan = useMemo(()=>findCurrentPlan(plans, planPeriodFrom, planPeriodTo, planProduct, planSource, planType), [
        plans,
        planPeriodFrom,
        planPeriodTo,
        planProduct,
        planSource,
        planType
    ]);
    const filteredConnections = useMemo(()=>connections.filter((connection)=>connection.category === connectionCategory), [
        connections,
        connectionCategory
    ]);
    const adsConnections = useMemo(()=>connections.filter((connection)=>connection.category === "ads"), [
        connections
    ]);
    const crmConnections = useMemo(()=>connections.filter((connection)=>connection.category === "crm"), [
        connections
    ]);
    const currentConnectionPlatforms = connectionCategory === "crm" ? CRM_CONNECTION_PLATFORMS : ADS_CONNECTION_PLATFORMS;
    const tablePlans = useMemo(()=>plans.filter((plan)=>planMatchesFilters(plan, activePlanProduct, activePlanSource, activePlanType)), [
        plans,
        activePlanProduct,
        activePlanSource,
        activePlanType
    ]);
    const currentTable = useMemo(()=>{
        const table = buildTable(filteredRecords, activeTab, grouping, tablePlans, appliedDateFrom, appliedDateTo, activePlanProduct, activePlanSource, activePlanType);
        return {
            ...table,
            rows: sortTableRows(table.rows, tableSort, activeTab, grouping)
        };
    }, [
        filteredRecords,
        activeTab,
        grouping,
        tableSort,
        tablePlans,
        appliedDateFrom,
        appliedDateTo,
        activePlanProduct,
        activePlanSource,
        activePlanType
    ]);
    const graphRows = useMemo(()=>buildGraphRows(filteredRecords, graphMetric, graphGrouping, appliedDateFrom, appliedDateTo), [
        filteredRecords,
        graphMetric,
        graphGrouping,
        appliedDateFrom,
        appliedDateTo
    ]);
    const graphMetricLabel = useMemo(()=>{
        var _GRAPH_METRICS_find;
        var _GRAPH_METRICS_find_label;
        return (_GRAPH_METRICS_find_label = (_GRAPH_METRICS_find = GRAPH_METRICS.find((item)=>item.key === graphMetric)) === null || _GRAPH_METRICS_find === void 0 ? void 0 : _GRAPH_METRICS_find.label) !== null && _GRAPH_METRICS_find_label !== void 0 ? _GRAPH_METRICS_find_label : "Расход";
    }, [
        graphMetric
    ]);
    const graphSvg = useMemo(()=>{
        if (!graphRows.length) return null;
        const width = 1080;
        const height = 400;
        const paddingLeft = 64;
        const paddingRight = 24;
        const paddingTop = 16;
        const paddingBottom = 56;
        const innerWidth = width - paddingLeft - paddingRight;
        const innerHeight = height - paddingTop - paddingBottom;
        const maxValue = Math.max(...graphRows.map((row)=>row.value), 0);
        const minValue = Math.min(...graphRows.map((row)=>row.value), 0);
        const range = maxValue - minValue || 1;
        const points = graphRows.map((row, index)=>{
            const x = graphRows.length === 1 ? paddingLeft + innerWidth / 2 : paddingLeft + innerWidth / Math.max(graphRows.length - 1, 1) * index;
            const y = paddingTop + (1 - (row.value - minValue) / range) * innerHeight;
            return {
                ...row,
                x,
                y,
                index
            };
        });
        const line = points.map((point, index)=>"".concat(index === 0 ? "M" : "L", " ").concat(point.x, " ").concat(point.y)).join(" ");
        const area = "".concat(line, " L ").concat(points[points.length - 1].x, " ").concat(height - paddingBottom, " L ").concat(points[0].x, " ").concat(height - paddingBottom, " Z");
        const yTicks = Array.from({
            length: 5
        }, (_, idx)=>{
            const ratio = idx / 4;
            const value = maxValue - range * ratio;
            const y = paddingTop + innerHeight * ratio;
            return {
                value,
                y
            };
        });
        const xLabelCount = Math.min(graphGrouping === "день" ? 9 : graphGrouping === "неделя" ? 7 : 6, points.length);
        const xLabelIndices = new Set();
        if (points.length === 1) {
            xLabelIndices.add(0);
        } else {
            const step = Math.max(1, Math.ceil(points.length / Math.max(xLabelCount, 1)));
            for(let idx = 0; idx < points.length; idx += step){
                xLabelIndices.add(idx);
            }
            xLabelIndices.add(points.length - 1);
        }
        return {
            width,
            height,
            paddingLeft,
            paddingRight,
            paddingBottom,
            points,
            line,
            area,
            yTicks,
            xLabelIndices
        };
    }, [
        graphRows
    ]);
    const planCpl = useMemo(()=>{
        const budget = Number(planBudget || 0);
        const leads = Number(planLeads || 0);
        return leads > 0 ? budget / leads : 0;
    }, [
        planBudget,
        planLeads
    ]);
    function updateImportState(target, rows, fileName, mapping) {
        const mapped = remapImportedRows(rows, target, mapping);
        const columns = rows.length ? Object.keys(rows[0] ?? {}) : [];
        if (target === "ads") {
            setAdsRawRows(rows);
            setAdsColumns(columns);
            setAdsMapping(mapping);
            setAdsRows(mapped);
            setAdsFileName(fileName);
        } else {
            setCrmRawRows(rows);
            setCrmColumns(columns);
            setCrmMapping(mapping);
            setCrmRows(mapped);
            setCrmFileName(fileName);
        }
        return mapped;
    }
    function handleMappingChange(target, fieldKey, columnName) {
        setError(null);
        setImportMessage(null);
        if (target === "ads") {
            const nextMapping = {
                ...adsMapping,
                [fieldKey]: columnName
            };
            const mapped = remapImportedRows(adsRawRows, "ads", nextMapping);
            setAdsMapping(nextMapping);
            setAdsRows(mapped);
            if (adsFileName) {
                setImportMessage('Файл "'.concat(adsFileName, '" подготовлен: прочитано ').concat(adsRawRows.length, ', распознано ').concat(mapped.length, '.'));
            }
            return;
        }
        const nextMapping = {
            ...crmMapping,
            [fieldKey]: columnName
        };
        const mapped = remapImportedRows(crmRawRows, "crm", nextMapping);
        setCrmMapping(nextMapping);
        setCrmRows(mapped);
        if (crmFileName) {
            setImportMessage('Файл "'.concat(crmFileName, '" подготовлен: прочитано ').concat(crmRawRows.length, ', распознано ').concat(mapped.length, '.'));
        }
    }
    useEffect(()=>{
        if (!currentPlan) return;
        setPlanBudget(String(currentPlan.budget || 0));
        setPlanLeads(String(currentPlan.leads || 0));
        setPlanProduct(currentPlan.product || "Все");
        setPlanSource(currentPlan.source || "Все");
        setPlanType(currentPlan.type || "Все");
    }, [
        currentPlan === null || currentPlan === void 0 ? void 0 : currentPlan.id
    ]);
    async function handleSourceFile(event, target) {
        var _event_target_files;
        const file = (_event_target_files = event.target.files) === null || _event_target_files === void 0 ? void 0 : _event_target_files[0];
        if (!file) return;
        try {
            setError(null);
            setImportMessage(null);
            const rows = await readStructuredRows(file);
            const columns = rows.length ? Object.keys(rows[0] ?? {}) : [];
            const mapping = inferImportMapping(columns, target);
            const mapped = updateImportState(target, rows, file.name, mapping);
            if (mapped.length > 0) {
                setImportMessage('Файл "'.concat(file.name, '" подготовлен: прочитано ').concat(rows.length, ', распознано ').concat(mapped.length, '. При необходимости проверь сопоставление колонок ниже.'));
            } else if (rows.length > 0) {
                const columnsPreview = columns.slice(0, 8).join(', ');
                setError('Файл "'.concat(file.name, '" прочитан, но строки не распознаны автоматически. Проверь сопоставление колонок ниже. Колонки: ').concat(columnsPreview || 'не определены', '.'));
            } else {
                setError('Файл "'.concat(file.name, '" прочитан, но в нем не найдено строк с данными.'));
            }
            event.target.value = "";
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось прочитать файл");
        }
    }
    async function handleImport() {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        if (adsRows.length === 0 && crmRows.length === 0) {
            setError("Сначала загрузите данные рекламы или CRM");
            return;
        }
        try {
            setImporting(true);
            setError(null);
            const result = await importProjectData(token, params.projectId, {
                ads_rows: adsRows,
                crm_rows: crmRows,
                replace_existing: replaceExisting
            });
            setImportMessage("Импорт завершен: реклама ".concat(result.ads_rows_imported, ", CRM ").concat(result.crm_rows_imported));
            setLoaderOpen(false);
            setLoading(true);
            await loadProject();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось импортировать данные");
        } finally{
            setImporting(false);
        }
    }
        function buildExportFileName(scope, format, tabLabel) {
        const safeProjectName = dashboard.project.name.replace(/[\\/:*?"<>|]+/g, "-").trim() || "report";
        const dateStamp = new Date().toISOString().slice(0, 10);
        if (scope === "current") {
            return `${safeProjectName}_${tabLabel}_${dateStamp}.${format}`;
        }
        return `${safeProjectName}_all-tabs_${dateStamp}.${format}`;
    }
    function downloadBlob(blob, fileName) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }
    function buildExportAoA(headers, rows) {
        return [
            headers,
            ...rows.map((row)=>row.values)
        ];
    }
    function exportCurrentReport(format) {
        if (activeTab === "graph" || activeTab === "plan") {
            setError("Для вкладок «Графики» и «План» используй выгрузку табличных вкладок.");
            return;
        }
        const tabLabel = TABS.find((tab)=>tab.key === activeTab)?.label || "report";
        const headers = currentTable.headers;
        const rows = currentTable.rows;
        if (!headers.length || !rows.length) {
            setError("Нет данных для экспорта.");
            return;
        }
        if (format === "xlsx") {
            const workbook = XLSX.utils.book_new();
            const worksheet = XLSX.utils.aoa_to_sheet(buildExportAoA(headers, rows));
            XLSX.utils.book_append_sheet(workbook, worksheet, tabLabel.slice(0, 31));
            XLSX.writeFile(workbook, buildExportFileName("current", "xlsx", activeTab));
            return;
        }
        const csv = XLSX.utils.sheet_to_csv(XLSX.utils.aoa_to_sheet(buildExportAoA(headers, rows)));
        downloadBlob(new Blob(["\uFEFF", csv], {
            type: "text/csv;charset=utf-8;"
        }), buildExportFileName("current", "csv", activeTab));
    }
    function exportAllReports(format) {
        const tables = EXPORTABLE_TABS.map((tab)=>{
            const table = buildTable(filteredRecords, tab.key, grouping, tablePlans, appliedDateFrom, appliedDateTo, activePlanProduct, activePlanSource, activePlanType);
            return {
                label: tab.label,
                key: tab.key,
                headers: table.headers,
                rows: table.rows
            };
        }).filter((table)=>table.headers.length && table.rows.length);
        if (!tables.length) {
            setError("Нет данных для экспорта.");
            return;
        }
        if (format === "xlsx") {
            const workbook = XLSX.utils.book_new();
            tables.forEach((table)=>{
                const worksheet = XLSX.utils.aoa_to_sheet(buildExportAoA(table.headers, table.rows));
                XLSX.utils.book_append_sheet(workbook, worksheet, table.label.slice(0, 31));
            });
            XLSX.writeFile(workbook, buildExportFileName("all", "xlsx", "all-tabs"));
            return;
        }
        const csvParts = tables.map((table)=>{
            const csv = XLSX.utils.sheet_to_csv(XLSX.utils.aoa_to_sheet(buildExportAoA(table.headers, table.rows)));
            return `${table.label}\r\n${csv}`;
        });
        downloadBlob(new Blob(["\uFEFF", csvParts.join("\r\n\r\n")], {
            type: "text/csv;charset=utf-8;"
        }), buildExportFileName("all", "csv", "all-tabs"));
    }
    async function handleSavePlan() {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        if (!planPeriodFrom || !planPeriodTo) {
            setError("Сначала выберите период плана");
            return;
        }
        try {
            setPlanLoading(true);
            setError(null);
            const saved = await saveProjectPlan(token, params.projectId, {
                period_from: planPeriodFrom,
                period_to: planPeriodTo,
                product: planProduct,
                source: planSource,
                type: planType,
                budget: Number(planBudget || 0),
                leads: Number(planLeads || 0)
            });
            setPlans((current)=>{
                const rest = current.filter((plan)=>plan.id !== saved.id);
                return [
                    saved,
                    ...rest
                ].sort((a, b)=>b.period_from.localeCompare(a.period_from));
            });
            setActiveTab("plan");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось сохранить план");
        } finally{
            setPlanLoading(false);
        }
    }
    async function handleDeletePlan(planId) {
        const token = getStoredToken();
        if (!token) {
            router.replace("/login");
            return;
        }
        if (!window.confirm("Удалить этот план?")) return;
        try {
            await deleteProjectPlan(token, params.projectId, planId);
            setPlans((current)=>current.filter((plan)=>plan.id !== planId));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось удалить план");
        }
    }
    function applyPeriod() {
        setAppliedDateFrom(draftDateFrom);
        setAppliedDateTo(draftDateTo);
    }
    function useReportPeriodForPlan() {
        setPlanPeriodFrom(appliedDateFrom || draftDateFrom);
        setPlanPeriodTo(appliedDateTo || draftDateTo);
    }
    function toggleTableSort(columnIndex) {
        setTableSort((current)=>{
            if (!current || current.columnIndex != columnIndex) return {
                columnIndex,
                direction: "asc"
            };
            return {
                columnIndex,
                direction: current.direction === "asc" ? "desc" : "asc"
            };
        });
    }
    function getFilterSummary(key) {
        const total = filterOptions[key];
        const selected = filterState[key];
        const selectedVisible = selected.filter((option)=>total.includes(option));
        if (!total.length) return "Нет данных";
        if (!selectedVisible.length) return "Ничего";
        if (selectedVisible.length === total.length) return "Все";
        if (selectedVisible.length === 1) return selectedVisible[0];
        return "".concat(selectedVisible.length, " Ничего?");
    }
    function toggleFilterOption(key, option) {
        setFilterState((current)=>({
                ...current,
                [key]: current[key].includes(option) ? current[key].filter((item)=>item !== option) : [
                    ...current[key],
                    option
                ]
            }));
    }
    function setAllFilterOptions(key, mode) {
        setFilterState((current)=>({
                ...current,
                [key]: mode === "all" ? [
                    ...filterOptions[key]
                ] : []
            }));
    }
    if (loading) return /*#__PURE__*/ _jsx("main", {
        className: "page-wrap",
        children: "Загрузка проекта..."
    });
    if (!dashboard) return /*#__PURE__*/ _jsx("main", {
        className: "page-wrap",
        children: "Проект не найден."
    });
    var _connectionForm_platform, _connectionForm_name, _connectionForm_identifier, _connectionForm_api_mode, _connectionForm_client_login_mode, _connectionForm_token, _connectionForm_client_id, _connectionForm_client_secret, _connectionForm_refresh_token;
    return /*#__PURE__*/ _jsxs("main", {
        className: "page-wrap",
        children: [
            connectionsOpen ? /*#__PURE__*/ _jsx("div", {
                className: "modal-overlay",
                onClick: ()=>setConnectionsOpen(false),
                children: /*#__PURE__*/ _jsxs("div", {
                    className: "loader-modal connection-modal",
                    onClick: (event)=>event.stopPropagation(),
                    children: [
                        /*#__PURE__*/ _jsxs("div", {
                            className: "loader-modal__header",
                            children: [
                                /*#__PURE__*/ _jsxs("div", {
                                    children: [
                                        /*#__PURE__*/ _jsx("h3", {
                                            children: "Подключения проекта"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Настрой и проверь рекламные кабинеты и CRM"
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsx("button", {
                                    className: "ghost-btn",
                                    type: "button",
                                    onClick: ()=>setConnectionsOpen(false),
                                    children: "Закрыть"
                                })
                            ]
                        }),
                        /*#__PURE__*/ _jsxs("div", {
                            className: "connection-category-tabs",
                            children: [
                                /*#__PURE__*/ _jsx("button", {
                                    className: "desktop-tab ".concat(connectionCategory === "ads" ? "active" : ""),
                                    type: "button",
                                    onClick: ()=>resetConnectionForm("ads"),
                                    children: "Рекламные кабинеты"
                                }),
                                /*#__PURE__*/ _jsx("button", {
                                    className: "desktop-tab ".concat(connectionCategory === "crm" ? "active" : ""),
                                    type: "button",
                                    onClick: ()=>resetConnectionForm("crm"),
                                    children: "CRM-системы"
                                })
                            ]
                        }),
                        /*#__PURE__*/ _jsxs("div", {
                            className: "connection-layout",
                            children: [
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "connection-list",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Подключения"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "connection-list-items",
                                            children: filteredConnections.map((connection)=>/*#__PURE__*/ _jsxs("button", {
                                                    type: "button",
                                                    className: "connection-list-item ".concat(editingConnectionId === connection.id ? "is-active" : ""),
                                                    onClick: ()=>editConnection(connection),
                                                    children: [
                                                        /*#__PURE__*/ _jsxs("div", {
                                                            children: [
                                                                /*#__PURE__*/ _jsx("strong", {
                                                                    children: connection.name
                                                                }),
                                                                /*#__PURE__*/ _jsx("div", {
                                                                    className: "import-subtitle",
                                                                    children: connection.platform === "yandex_direct" ? "Яндекс.Директ" : connection.platform
                                                                })
                                                            ]
                                                        }),
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "connection-status connection-status--".concat(connection.status),
                                                            children: connection.status === "connected" ? "Подключен" : connection.status === "error" ? "Ошибка" : "Не проверен"
                                                        })
                                                    ]
                                                }, connection.id))
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "actions-row connection-list-actions",
                                            children: [
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "ghost-btn",
                                                    type: "button",
                                                    onClick: ()=>resetConnectionForm(connectionCategory),
                                                    children: "Новое подключение"
                                                }),
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "ghost-btn",
                                                    type: "button",
                                                    onClick: ()=>void loadConnections(),
                                                    disabled: connectionsLoading,
                                                    children: connectionsLoading ? "Обновляем..." : "Обновить"
                                                })
                                            ]
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "connection-form-card",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Настройка подключения"
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "desktop-filters-grid connection-grid",
                                            children: [
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Платформа"
                                                        }),
                                                        /*#__PURE__*/ _jsx("select", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_platform = connectionForm.platform) !== null && _connectionForm_platform !== void 0 ? _connectionForm_platform : connectionCategory === "crm" ? "amocrm" : "yandex_direct",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        category: connectionCategory,
                                                                        platform: event.target.value
                                                                    })),
                                                            children: currentConnectionPlatforms.map((option)=>/*#__PURE__*/ _jsx("option", {
                                                                    value: option.key,
                                                                    children: option.label
                                                                }, option.key))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Название"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_name = connectionForm.name) !== null && _connectionForm_name !== void 0 ? _connectionForm_name : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        name: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: connectionCategory === "crm" ? "Портал / webhook" : "ID / логин"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_identifier = connectionForm.identifier) !== null && _connectionForm_identifier !== void 0 ? _connectionForm_identifier : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        identifier: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Режим API"
                                                        }),
                                                        /*#__PURE__*/ _jsxs("select", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_api_mode = connectionForm.api_mode) !== null && _connectionForm_api_mode !== void 0 ? _connectionForm_api_mode : "production",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        api_mode: event.target.value
                                                                    })),
                                                            children: [
                                                                /*#__PURE__*/ _jsx("option", {
                                                                    value: "production",
                                                                    children: "Боевой"
                                                                }),
                                                                /*#__PURE__*/ _jsx("option", {
                                                                    value: "sandbox",
                                                                    children: "Тестовый (sandbox)"
                                                                })
                                                            ]
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Client-Login"
                                                        }),
                                                        /*#__PURE__*/ _jsxs("select", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_client_login_mode = connectionForm.client_login_mode) !== null && _connectionForm_client_login_mode !== void 0 ? _connectionForm_client_login_mode : "auto",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        client_login_mode: event.target.value
                                                                    })),
                                                            children: [
                                                                /*#__PURE__*/ _jsx("option", {
                                                                    value: "auto",
                                                                    children: "Авто"
                                                                }),
                                                                /*#__PURE__*/ _jsx("option", {
                                                                    value: "always",
                                                                    children: "Всегда использовать"
                                                                }),
                                                                /*#__PURE__*/ _jsx("option", {
                                                                    value: "never",
                                                                    children: "Не использовать"
                                                                })
                                                            ]
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Токен"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_token = connectionForm.token) !== null && _connectionForm_token !== void 0 ? _connectionForm_token : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        token: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Client ID"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_client_id = connectionForm.client_id) !== null && _connectionForm_client_id !== void 0 ? _connectionForm_client_id : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        client_id: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Client Secret"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_client_secret = connectionForm.client_secret) !== null && _connectionForm_client_secret !== void 0 ? _connectionForm_client_secret : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        client_secret: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "desktop-filter",
                                                    children: [
                                                        /*#__PURE__*/ _jsx("span", {
                                                            className: "desktop-filter__label",
                                                            children: "Refresh Token"
                                                        }),
                                                        /*#__PURE__*/ _jsx("input", {
                                                            className: "desktop-input",
                                                            value: (_connectionForm_refresh_token = connectionForm.refresh_token) !== null && _connectionForm_refresh_token !== void 0 ? _connectionForm_refresh_token : "",
                                                            onChange: (event)=>setConnectionForm((current)=>({
                                                                        ...current,
                                                                        refresh_token: event.target.value
                                                                    }))
                                                        })
                                                    ]
                                                })
                                            ]
                                        }),
                                        error ? /*#__PURE__*/ _jsx("div", {
                                            className: "error-banner connection-form-error",
                                            children: error
                                        }) : null,
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "plan-form-footer",
                                            children: [
                                                /*#__PURE__*/ _jsx("div", {
                                                    className: "import-subtitle",
                                                    children: editingConnectionId ? "Редактируешь существующее подключение." : connectionCategory === "crm" ? "Создай новое подключение CRM-системы." : "Создай новое подключение рекламного кабинета."
                                                }),
                                                /*#__PURE__*/ _jsxs("div", {
                                                    className: "actions-row",
                                                    children: [
                                                        editingConnectionId ? /*#__PURE__*/ _jsx("button", {
                                                            className: "ghost-btn",
                                                            type: "button",
                                                            onClick: ()=>void handleDeleteConnection(editingConnectionId),
                                                            children: "Удалить"
                                                        }) : null,
                                                        editingConnectionId ? /*#__PURE__*/ _jsx("button", {
                                                            className: "ghost-btn",
                                                            type: "button",
                                                            onClick: ()=>void handleTestConnection(editingConnectionId),
                                                            disabled: connectionTestingId === editingConnectionId,
                                                            children: connectionTestingId === editingConnectionId ? "Проверяем..." : "Проверить подключение"
                                                        }) : null,
                                                        /*#__PURE__*/ _jsx("button", {
                                                            className: "primary-btn",
                                                            type: "button",
                                                            onClick: ()=>void handleSaveConnection(),
                                                            disabled: connectionSaving,
                                                            children: connectionSaving ? "Сохраняем..." : "Сохранить"
                                                        })
                                                    ]
                                                })
                                            ]
                                        })
                                    ]
                                })
                            ]
                        })
                    ]
                })
            }) : null,
            loaderOpen ? /*#__PURE__*/ _jsx("div", {
                className: "modal-overlay",
                onClick: ()=>setLoaderOpen(false),
                children: /*#__PURE__*/ _jsxs("div", {
                    className: "loader-modal",
                    onClick: (event)=>event.stopPropagation(),
                    children: [
                        /*#__PURE__*/ _jsxs("div", {
                            className: "loader-modal__header",
                            children: [
                                /*#__PURE__*/ _jsxs("div", {
                                    children: [
                                        /*#__PURE__*/ _jsx("h3", {
                                            children: "Загрузка и объединение данных"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Можно загрузить данные из файлов и затем объединить рекламу и CRM внутри проекта."
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsx("button", {
                                    className: "ghost-btn",
                                    type: "button",
                                    onClick: ()=>setLoaderOpen(false),
                                    children: "Закрыть"
                                })
                            ]
                        }),
                        /*#__PURE__*/ _jsxs("div", {
                            className: "loader-summary-card",
                            children: [
                                /*#__PURE__*/ _jsx("div", {
                                    className: "loader-summary-title",
                                    children: "Выбранные файлы"
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "loader-summary-line",
                                    children: [
                                        "Реклама: ",
                                        adsFileName ? "".concat(adsFileName, " (").concat(adsRows.length, " строк)") : "файл не выбран (не загружено)"
                                    ]
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "loader-summary-line",
                                    children: [
                                        "CRM: ",
                                        crmFileName ? "".concat(crmFileName, " (").concat(crmRows.length, " строк)") : "файл не выбран (не загружено)"
                                    ]
                                })
                            ]
                        }),
                        /*#__PURE__*/ _jsx("div", {
                            className: "loader-hint",
                            children: "Сначала загрузите файл рекламы и файл CRM, затем нажмите \xabОбъединить данные\xbb."
                        }),
                        /*#__PURE__*/ _jsx("div", {
                            className: "loader-section-title",
                            children: "Загрузка из файлов"
                        }),
                        /*#__PURE__*/ _jsxs("div", {
                            className: "loader-modal__grid",
                            children: [
                                /*#__PURE__*/ _jsx(ImportFileCard, {
                                    title: "Реклама",
                                    buttonLabel: "Загрузить данные рекламы",
                                    fileName: adsFileName,
                                    rawRowCount: adsRawRows.length,
                                    mappedRowCount: adsRows.length,
                                    columns: adsColumns,
                                    mapping: adsMapping,
                                    fields: ADS_IMPORT_FIELDS,
                                    previewRows: adsRawRows.slice(0, 3),
                                    onFileChange: (event)=>void handleSourceFile(event, "ads"),
                                    onMappingChange: (fieldKey, columnName)=>handleMappingChange("ads", fieldKey, columnName)
                                }),
                                /*#__PURE__*/ _jsx(ImportFileCard, {
                                    title: "CRM",
                                    buttonLabel: "Загрузить данные CRM",
                                    fileName: crmFileName,
                                    rawRowCount: crmRawRows.length,
                                    mappedRowCount: crmRows.length,
                                    columns: crmColumns,
                                    mapping: crmMapping,
                                    fields: CRM_IMPORT_FIELDS,
                                    previewRows: crmRawRows.slice(0, 3),
                                    onFileChange: (event)=>void handleSourceFile(event, "crm"),
                                    onMappingChange: (fieldKey, columnName)=>handleMappingChange("crm", fieldKey, columnName)
                                })
                            ]
                        }),
                        /*#__PURE__*/ _jsxs("label", {
                            className: "checkbox-row",
                            children: [
                                /*#__PURE__*/ _jsx("input", {
                                    checked: replaceExisting,
                                    type: "checkbox",
                                    onChange: (event)=>setReplaceExisting(event.target.checked)
                                }),
                                "Заменить существующие данные проекта"
                            ]
                        }),
                        /*#__PURE__*/ _jsxs("div", {
                            className: "actions-row",
                            children: [
                                /*#__PURE__*/ _jsx("button", {
                                    className: "primary-btn",
                                    type: "button",
                                    onClick: ()=>void handleImport(),
                                    disabled: importing,
                                    children: importing ? "Объединяем..." : "Объединить данные"
                                }),
                                importMessage ? /*#__PURE__*/ _jsx("span", {
                                    className: "success-text",
                                    children: importMessage
                                }) : null
                            ]
                        })
                    ]
                })
            }) : null,
            /*#__PURE__*/ _jsxs("div", {
                className: "project-shell ".concat(sidebarCollapsed ? "project-shell--sidebar-collapsed" : "").concat(isClientUser ? " project-shell--client" : ""),
                children: [
                    /*#__PURE__*/ _jsx("aside", {
                        className: "sidebar-card project-sidebar ".concat(sidebarCollapsed ? "is-collapsed" : ""),
                        children: !sidebarCollapsed ? /*#__PURE__*/ _jsxs(_Fragment, {
                            children: [
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-toggle-row",
                                    children: [
                                        /*#__PURE__*/ _jsx("button", {
                                            className: "ghost-btn sidebar-toggle-btn",
                                            type: "button",
                                            onClick: ()=>setSidebarCollapsed(true),
                                            "aria-label": "Свернуть боковую панель",
                                            title: "Свернуть боковую панель",
                                            children: /*#__PURE__*/ _jsx("img", {
                                                className: "sidebar-toggle-icon-image",
                                                src: "/icons/sidebar-toggle.png",
                                                alt: "",
                                                "aria-hidden": "true"
                                            })
                                        }),
                                        /*#__PURE__*/ _jsxs(Link, {
                                            className: "ghost-btn sidebar-back-btn",
                                            href: "/projects",
                                            children: [
                                                "← ",
                                                /*#__PURE__*/ _jsx("span", {
                                                    children: "Назад"
                                                })
                                            ]
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsx("div", {
                                    className: "sidebar-section sidebar-section--status",
                                    children: /*#__PURE__*/ _jsxs("div", {
                                        children: [
                                            /*#__PURE__*/ _jsx("h2", {
                                                className: "section-title",
                                                children: dashboard.project.name
                                            }),
                                            /*#__PURE__*/ _jsxs("div", {
                                                className: "project-status-list",
                                                children: [
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "project-status-item",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                children: "Период"
                                                            }),
                                                            /*#__PURE__*/ _jsx("strong", {
                                                                children: dashboard.period_label || "Период пока не определен"
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "project-status-item",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                children: "Обновлено"
                                                            }),
                                                            /*#__PURE__*/ _jsx("strong", {
                                                                children: formatDateTime(dashboard.project.updated_at)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "project-status-item",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                children: "Рекламных строк"
                                                            }),
                                                            /*#__PURE__*/ _jsx("strong", {
                                                                children: dashboard.records.filter((item)=>item.cost > 0).length
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "project-status-item",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                children: "CRM строк"
                                                            }),
                                                            /*#__PURE__*/ _jsx("strong", {
                                                                children: dashboard.records.filter((item)=>item.leads > 0 || item.sales > 0 || item.revenue > 0).length
                                                            })
                                                        ]
                                                    })
                                                ]
                                            })
                                        ]
                                    })
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-section",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Загрузка данных"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Загружай CSV, XLSX или JSON. После выбора файлов можно объединить рекламу и CRM в проект."
                                        }),
                                        /*#__PURE__*/ _jsx("button", {
                                            className: "primary-btn",
                                            type: "button",
                                            onClick: ()=>setLoaderOpen(true),
                                            children: "Загрузка данных"
                                        }),
                                        importMessage ? /*#__PURE__*/ _jsx("div", {
                                            className: "success-text",
                                            children: importMessage
                                        }) : null
                                    ]
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-section",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Рекламные кабинеты"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Подключай кабинеты проекта и проверяй их статус."
                                        }),
                                        /*#__PURE__*/ _jsx("button", {
                                            className: "ghost-btn",
                                            type: "button",
                                            onClick: ()=>{
                                                setConnectionsOpen(true);
                                                resetConnectionForm("ads");
                                            },
                                            children: "Подключения"
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "project-chip",
                                            children: [
                                                "Подключено: ",
                                                adsConnections.filter((item)=>item.status === "connected").length,
                                                " из ",
                                                adsConnections.length
                                            ]
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-section",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "CRM-системы"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Подключай AmoCRM и Bitrix24 для веб-отчета."
                                        }),
                                        /*#__PURE__*/ _jsx("button", {
                                            className: "ghost-btn",
                                            type: "button",
                                            onClick: ()=>{
                                                setConnectionsOpen(true);
                                                resetConnectionForm("crm");
                                            },
                                            children: "Подключения"
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "project-chip",
                                            children: [
                                                "Подключено: ",
                                                crmConnections.filter((item)=>item.status === "connected").length,
                                                " из ",
                                                crmConnections.length
                                            ]
                                        })
                                    ]
                                }),
                                /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-section",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Экспорт"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Выгрузи текущий отчет или все табличные вкладки в Xlsx и CSV, как в desktop-версии."
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "sidebar-export-grid",
                                            children: [
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "ghost-btn",
                                                    type: "button",
                                                    onClick: ()=>exportCurrentReport("xlsx"),
                                                    disabled: activeTab === "graph" || activeTab === "plan",
                                                    children: "Текущий отчет в Xlsx"
                                                }),
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "ghost-btn",
                                                    type: "button",
                                                    onClick: ()=>exportCurrentReport("csv"),
                                                    disabled: activeTab === "graph" || activeTab === "plan",
                                                    children: "Текущий отчет в CSV"
                                                }),
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "primary-btn",
                                                    type: "button",
                                                    onClick: ()=>exportAllReports("xlsx"),
                                                    children: "Все вкладки в Xlsx"
                                                }),
                                                /*#__PURE__*/ _jsx("button", {
                                                    className: "primary-btn",
                                                    type: "button",
                                                    onClick: ()=>exportAllReports("csv"),
                                                    children: "Все вкладки в CSV"
                                                })
                                            ]
                                        })
                                    ]
                                }),                                canManageProjectAccess ? /*#__PURE__*/ _jsxs("div", {
                                    className: "sidebar-section sidebar-section--access",
                                    className: "sidebar-section",
                                    children: [
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "section-title",
                                            children: "Доступ"
                                        }),
                                        /*#__PURE__*/ _jsx("div", {
                                            className: "import-subtitle",
                                            children: "Управляй ролями и доступом пользователей к этому проекту."
                                        }),
                                        /*#__PURE__*/ _jsx(Link, {
                                            className: "ghost-btn",
                                            href: "/users",
                                            children: "Управлять доступом"
                                        }),
                                        /*#__PURE__*/ _jsxs("div", {
                                            className: "project-chip",
                                            children: [
                                                "Участников: ",
                                                membersLoading ? "..." : members.length
                                            ]
                                        })
                                    ]
                                }) : null,
                            ]
                        }) : /*#__PURE__*/ _jsxs("div", {
                            className: "sidebar-collapsed-actions",
                            children: [
                                /*#__PURE__*/ _jsx("button", {
                                    className: "ghost-btn sidebar-mini-btn",
                                    type: "button",
                                    onClick: ()=>setSidebarCollapsed(false),
                                    title: "Развернуть боковую панель",
                                    "aria-label": "Развернуть боковую панель",
                                    children: /*#__PURE__*/ _jsx("img", {
                                        className: "sidebar-toggle-icon-image",
                                        src: "/icons/sidebar-toggle.png",
                                        alt: "",
                                        "aria-hidden": "true"
                                    })
                                }),
                                /*#__PURE__*/ _jsx(Link, {
                                    className: "ghost-btn sidebar-mini-btn",
                                    href: "/projects",
                                    title: "Назад",
                                    "aria-label": "Назад",
                                    children: "←"
                                }),
                                /*#__PURE__*/ _jsx("button", {
                                    className: "ghost-btn sidebar-mini-btn",
                                    type: "button",
                                    onClick: ()=>setLoaderOpen(true),
                                    title: "Загрузка данных",
                                    "aria-label": "Загрузка данных",
                                    children: "↓"
                                })
                            ]
                        })
                    }),
                    /*#__PURE__*/ _jsxs("section", {
                        className: "content-card dashboard-shell",
                        children: [
                            /*#__PURE__*/ _jsxs("div", {
                                className: "project-period-toolbar project-period-toolbar--desktop",
                                children: [
                                    /*#__PURE__*/ _jsxs("div", {
                                        className: "project-period-toolbar__group",
                                        children: [
                                            /*#__PURE__*/ _jsx("span", {
                                                className: "desktop-filter__label",
                                                children: "Период: с"
                                            }),
                                            /*#__PURE__*/ _jsx("input", {
                                                className: "desktop-input",
                                                type: "date",
                                                value: draftDateFrom,
                                                onChange: (event)=>setDraftDateFrom(event.target.value)
                                            })
                                        ]
                                    }),
                                    /*#__PURE__*/ _jsxs("div", {
                                        className: "project-period-toolbar__group",
                                        children: [
                                            /*#__PURE__*/ _jsx("span", {
                                                className: "desktop-filter__label",
                                                children: "по"
                                            }),
                                            /*#__PURE__*/ _jsx("input", {
                                                className: "desktop-input",
                                                type: "date",
                                                value: draftDateTo,
                                                onChange: (event)=>setDraftDateTo(event.target.value)
                                            })
                                        ]
                                    }),
                                    /*#__PURE__*/ _jsxs("div", {
                                        className: "project-period-toolbar__group",
                                        children: [
                                            /*#__PURE__*/ _jsx("span", {
                                                className: "desktop-filter__label",
                                                children: "Группировка"
                                            }),
                                            /*#__PURE__*/ _jsx("select", {
                                                className: "desktop-input",
                                                value: grouping,
                                                onChange: (event)=>setGrouping(event.target.value),
                                                children: GROUPINGS.map((option)=>/*#__PURE__*/ _jsx("option", {
                                                        value: option.key,
                                                        children: option.label
                                                    }, option.key))
                                            })
                                        ]
                                    }),
                                    /*#__PURE__*/ _jsx("div", {
                                        className: "project-period-toolbar__actions",
                                        children: /*#__PURE__*/ _jsx("button", {
                                            className: "primary-btn",
                                            type: "button",
                                            onClick: applyPeriod,
                                            children: "Применить"
                                        })
                                    })
                                ]
                            }),
                            /*#__PURE__*/ _jsx("div", {
                                className: "kpi-grid kpi-grid--desktop",
                                children: kpiCards.map((metric)=>/*#__PURE__*/ _jsxs("article", {
                                        className: "metric-card",
                                        children: [
                                            /*#__PURE__*/ _jsx("div", {
                                                className: "label",
                                                children: metric.label
                                            }),
                                            /*#__PURE__*/ _jsx("div", {
                                                className: "value",
                                                children: metric.value
                                            })
                                        ]
                                    }, metric.label))
                            }),
                            /*#__PURE__*/ _jsx("div", {
                                className: "desktop-filters-grid desktop-filters-grid--dropdowns",
                                children: FILTERS.map((filter)=>{
                                    const options = filterOptions[filter.key];
                                    const query = filterSearch[filter.key].toLowerCase();
                                    const visibleOptions = options.filter((option)=>option.toLowerCase().includes(query));
                                    return /*#__PURE__*/ _jsxs("div", {
                                        className: "desktop-filter desktop-filter--popup",
                                        children: [
                                            /*#__PURE__*/ _jsx("span", {
                                                className: "desktop-filter__label",
                                                children: filter.label
                                            }),
                                            /*#__PURE__*/ _jsx("button", {
                                                className: "desktop-filter__trigger",
                                                type: "button",
                                                onClick: ()=>setFilterOpen((current)=>({
                                                            ...buildInitialOpenState(),
                                                            ...current,
                                                            [filter.key]: !current[filter.key]
                                                        })),
                                                children: /*#__PURE__*/ _jsx("span", {
                                                    children: getFilterSummary(filter.key)
                                                })
                                            }),
                                            filterOpen[filter.key] ? /*#__PURE__*/ _jsxs("div", {
                                                className: "filter-popover",
                                                children: [
                                                    /*#__PURE__*/ _jsx("input", {
                                                        className: "desktop-input",
                                                        placeholder: "Поиск...",
                                                        value: filterSearch[filter.key],
                                                        onChange: (event)=>setFilterSearch((current)=>({
                                                                    ...current,
                                                                    [filter.key]: event.target.value
                                                                }))
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "filter-popover__actions",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("button", {
                                                                className: "ghost-btn",
                                                                type: "button",
                                                                onClick: ()=>setAllFilterOptions(filter.key, "all"),
                                                                children: "Выбрать все"
                                                            }),
                                                            /*#__PURE__*/ _jsx("button", {
                                                                className: "ghost-btn",
                                                                type: "button",
                                                                onClick: ()=>setAllFilterOptions(filter.key, "none"),
                                                                children: "Снять все"
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsx("div", {
                                                        className: "filter-popover__list",
                                                        children: visibleOptions.map((option)=>/*#__PURE__*/ _jsxs("label", {
                                                                className: "checkbox-row",
                                                                children: [
                                                                    /*#__PURE__*/ _jsx("input", {
                                                                        checked: filterState[filter.key].includes(option),
                                                                        type: "checkbox",
                                                                        onChange: ()=>toggleFilterOption(filter.key, option)
                                                                    }),
                                                                    /*#__PURE__*/ _jsx("span", {
                                                                        className: "checkbox-row__text",
                                                                        children: option
                                                                    })
                                                                ]
                                                            }, option))
                                                    })
                                                ]
                                            }) : null
                                        ]
                                    }, filter.key);
                                })
                            }),
                            /*#__PURE__*/ _jsx("div", {
                                className: "desktop-tabs-row",
                                children: TABS.map((tab)=>/*#__PURE__*/ _jsx("button", {
                                        type: "button",
                                        className: "desktop-tab ".concat(activeTab === tab.key ? "active" : ""),
                                        onClick: ()=>setActiveTab(tab.key),
                                        children: tab.label
                                    }, tab.key))
                            }),
                            activeTab === "graph" ? /*#__PURE__*/ _jsxs("section", {
                                className: "chart-card chart-card--embedded chart-card--desktop",
                                children: [
                                    /*#__PURE__*/ _jsxs("div", {
                                        className: "chart-toolbar",
                                        children: [
                                            /*#__PURE__*/ _jsxs("label", {
                                                className: "chart-toolbar__group",
                                                children: [
                                                    /*#__PURE__*/ _jsx("span", {
                                                        children: "Показатель"
                                                    }),
                                                    /*#__PURE__*/ _jsx("select", {
                                                        className: "desktop-input",
                                                        value: graphMetric,
                                                        onChange: (event)=>setGraphMetric(event.target.value),
                                                        children: GRAPH_METRICS.map((metric)=>/*#__PURE__*/ _jsx("option", {
                                                                value: metric.key,
                                                                children: metric.label
                                                            }, metric.key))
                                                    })
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsxs("label", {
                                                className: "chart-toolbar__group",
                                                children: [
                                                    /*#__PURE__*/ _jsx("span", {
                                                        children: "Группировка"
                                                    }),
                                                    /*#__PURE__*/ _jsx("select", {
                                                        className: "desktop-input",
                                                        value: graphGrouping,
                                                        onChange: (event)=>setGraphGrouping(event.target.value),
                                                        children: GROUPINGS.map((item)=>/*#__PURE__*/ _jsx("option", {
                                                                value: item.key,
                                                                children: item.label
                                                            }, item.key))
                                                    })
                                                ]
                                            })
                                        ]
                                    }),
                                    /*#__PURE__*/ _jsxs("div", {
                                        className: "chart-subtitle",
                                        children: [
                                            "График по показателю \xab",
                                            graphMetricLabel,
                                            "\xbb с учетом выбранных фильтров и группировки, как в desktop-версии."
                                        ]
                                    }),
                                    graphSvg ? /*#__PURE__*/ _jsx("div", {
                                        className: "chart-svg-wrap",
                                        children: /*#__PURE__*/ _jsxs("svg", {
                                            className: "chart-svg",
                                            viewBox: "0 0 ".concat(graphSvg.width, " ").concat(graphSvg.height),
                                            preserveAspectRatio: "none",
                                            role: "img",
                                            "aria-label": "График ".concat(graphMetricLabel),
                                            children: [
                                                graphSvg.yTicks.map((tick, index)=>/*#__PURE__*/ _jsxs("g", {
                                                        children: [
                                                            /*#__PURE__*/ _jsx("line", {
                                                                className: "chart-svg__grid",
                                                                x1: graphSvg.paddingLeft,
                                                                y1: tick.y,
                                                                x2: graphSvg.width - graphSvg.paddingRight,
                                                                y2: tick.y
                                                            }),
                                                            /*#__PURE__*/ _jsx("text", {
                                                                className: "chart-svg__axis-value",
                                                                x: 10,
                                                                y: tick.y + 4,
                                                                textAnchor: "start",
                                                                children: formatGraphMetricValue(graphMetric, tick.value)
                                                            })
                                                        ]
                                                    }, index)),
                                                /*#__PURE__*/ _jsx("line", {
                                                    className: "chart-svg__baseline",
                                                    x1: graphSvg.paddingLeft,
                                                    y1: graphSvg.height - graphSvg.paddingBottom,
                                                    x2: graphSvg.width - graphSvg.paddingRight,
                                                    y2: graphSvg.height - graphSvg.paddingBottom
                                                }),
                                                /*#__PURE__*/ _jsx("path", {
                                                    className: "chart-svg__area",
                                                    d: graphSvg.area
                                                }),
                                                /*#__PURE__*/ _jsx("path", {
                                                    className: "chart-svg__line",
                                                    d: graphSvg.line
                                                }),
                                                graphSvg.points.map((point, index)=>/*#__PURE__*/ _jsxs("g", {
                                                        children: [
                                                            /*#__PURE__*/ _jsx("circle", {
                                                                className: "chart-svg__hit",
                                                                cx: point.x,
                                                                cy: point.y,
                                                                r: 8,
                                                                children: /*#__PURE__*/ _jsx("title", {
                                                                    children: "".concat(point.label, ": ").concat(formatGraphMetricValue(graphMetric, point.value))
                                                                })
                                                            }),
                                                            graphSvg.xLabelIndices.has(index) ? /*#__PURE__*/ _jsx("text", {
                                                                className: "chart-svg__label",
                                                                x: point.x,
                                                                y: graphSvg.height - 18,
                                                                textAnchor: index === 0 ? "start" : index === graphSvg.points.length - 1 ? "end" : "middle",
                                                                children: formatGraphAxisLabel(point.label, graphGrouping)
                                                            }) : null
                                                        ]
                                                    }, point.label))
                                            ]
                                        })
                                    }) : /*#__PURE__*/ _jsx("div", {
                                        className: "chart-empty",
                                        children: "Нет данных для построения графика за выбранный период."
                                    })
                                ]
                            }) : activeTab === "plan" ? /*#__PURE__*/ _jsxs("section", {
                                className: "plan-layout plan-layout--enhanced",
                                children: [
                                    /*#__PURE__*/ _jsxs("article", {
                                        className: "plan-card plan-card--form",
                                        children: [
                                            /*#__PURE__*/ _jsx("h3", {
                                                children: "Настроить план"
                                            }),
                                            /*#__PURE__*/ _jsxs("div", {
                                                className: "desktop-filters-grid plan-grid",
                                                children: [
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Период с"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                type: "date",
                                                                value: planPeriodFrom,
                                                                onChange: (event)=>setPlanPeriodFrom(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Период по"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                type: "date",
                                                                value: planPeriodTo,
                                                                onChange: (event)=>setPlanPeriodTo(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Продукт"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                list: "plan-product-options",
                                                                value: planProduct,
                                                                onChange: (event)=>setPlanProduct(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Источник"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                list: "plan-source-options",
                                                                value: planSource,
                                                                onChange: (event)=>setPlanSource(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Тип"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                list: "plan-type-options",
                                                                value: planType,
                                                                onChange: (event)=>setPlanType(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Расход план"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                type: "number",
                                                                value: planBudget,
                                                                onChange: (event)=>setPlanBudget(event.target.value)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "desktop-filter",
                                                        children: [
                                                            /*#__PURE__*/ _jsx("span", {
                                                                className: "desktop-filter__label",
                                                                children: "Лиды план"
                                                            }),
                                                            /*#__PURE__*/ _jsx("input", {
                                                                className: "desktop-input",
                                                                type: "number",
                                                                value: planLeads,
                                                                onChange: (event)=>setPlanLeads(event.target.value)
                                                            })
                                                        ]
                                                    })
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsxs("datalist", {
                                                id: "plan-product-options",
                                                children: [
                                                    /*#__PURE__*/ _jsx("option", {
                                                        value: "Все"
                                                    }),
                                                    filterOptions.product.map((option)=>/*#__PURE__*/ _jsx("option", {
                                                            value: option
                                                        }, option))
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsxs("datalist", {
                                                id: "plan-source-options",
                                                children: [
                                                    /*#__PURE__*/ _jsx("option", {
                                                        value: "Все"
                                                    }),
                                                    filterOptions.source.map((option)=>/*#__PURE__*/ _jsx("option", {
                                                            value: option
                                                        }, option))
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsxs("datalist", {
                                                id: "plan-type-options",
                                                children: [
                                                    /*#__PURE__*/ _jsx("option", {
                                                        value: "Все"
                                                    }),
                                                    filterOptions.type.map((option)=>/*#__PURE__*/ _jsx("option", {
                                                            value: option
                                                        }, option))
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsxs("div", {
                                                className: "plan-form-footer",
                                                children: [
                                                    /*#__PURE__*/ _jsxs("div", {
                                                        className: "plan-cpl-badge",
                                                        children: [
                                                            "CPL план: ",
                                                            /*#__PURE__*/ _jsx("strong", {
                                                                children: formatInt(planCpl)
                                                            })
                                                        ]
                                                    }),
                                                    /*#__PURE__*/ _jsx("div", {
                                                        className: "actions-row",
                                                        children: /*#__PURE__*/ _jsx("button", {
                                                            className: "primary-btn",
                                                            type: "button",
                                                            onClick: ()=>void handleSavePlan(),
                                                            disabled: planLoading,
                                                            children: planLoading ? "Сохраняем..." : "Сохранить план"
                                                        })
                                                    })
                                                ]
                                            })
                                        ]
                                    }),
                                    /*#__PURE__*/ _jsxs("article", {
                                        className: "plan-card plan-card--history",
                                        children: [
                                            /*#__PURE__*/ _jsxs("div", {
                                                className: "plan-card__header",
                                                children: [
                                                    /*#__PURE__*/ _jsx("h3", {
                                                        children: "История планов"
                                                    }),
                                                    /*#__PURE__*/ _jsx("div", {
                                                        className: "import-subtitle",
                                                        children: "Можно загрузить сохраненный план в форму или удалить его."
                                                    })
                                                ]
                                            }),
                                            /*#__PURE__*/ _jsx("div", {
                                                className: "plan-history-list",
                                                children: plans.length === 0 ? /*#__PURE__*/ _jsx("div", {
                                                    className: "project-chip",
                                                    children: "Планов пока нет"
                                                }) : plans.map((plan)=>/*#__PURE__*/ _jsxs("div", {
                                                        className: "plan-history-item",
                                                        children: [
                                                            /*#__PURE__*/ _jsxs("div", {
                                                                className: "plan-history-item__main",
                                                                children: [
                                                                    /*#__PURE__*/ _jsxs("div", {
                                                                        className: "plan-history-item__title",
                                                                        children: [
                                                                            plan.period_from,
                                                                            " - ",
                                                                            plan.period_to
                                                                        ]
                                                                    }),
                                                                    /*#__PURE__*/ _jsxs("div", {
                                                                        className: "plan-history-item__meta",
                                                                        children: [
                                                                            "Продукт: ",
                                                                            plan.product || "Все",
                                                                            " • Источник: ",
                                                                            plan.source,
                                                                            " • Тип: ",
                                                                            plan.type,
                                                                            " • Бюджет: ",
                                                                            formatInt(plan.budget),
                                                                            " • Лиды: ",
                                                                            formatInt(plan.leads)
                                                                        ]
                                                                    })
                                                                ]
                                                            }),
                                                            /*#__PURE__*/ _jsxs("div", {
                                                                className: "actions-row",
                                                                children: [
                                                                    /*#__PURE__*/ _jsx("button", {
                                                                        className: "ghost-btn",
                                                                        type: "button",
                                                                        onClick: ()=>{
                                                                            setPlanPeriodFrom(plan.period_from);
                                                                            setPlanPeriodTo(plan.period_to);
                                                                            setPlanProduct(plan.product || "Все");
                                                                            setPlanSource(plan.source);
                                                                            setPlanType(plan.type);
                                                                            setPlanBudget(String(plan.budget));
                                                                            setPlanLeads(String(plan.leads));
                                                                        },
                                                                        children: "Загрузить"
                                                                    }),
                                                                    /*#__PURE__*/ _jsx("button", {
                                                                        className: "ghost-btn",
                                                                        type: "button",
                                                                        onClick: ()=>void handleDeletePlan(plan.id),
                                                                        children: "Удалить"
                                                                    })
                                                                ]
                                                            })
                                                        ]
                                                    }, plan.id))
                                            })
                                        ]
                                    })
                                ]
                            }) : /*#__PURE__*/ _jsx("div", {
                                className: "dashboard-table-wrap",
                                children: /*#__PURE__*/ _jsxs("table", {
                                    className: "dashboard-table",
                                    children: [
                                        /*#__PURE__*/ _jsx("thead", {
                                            children: /*#__PURE__*/ _jsx("tr", {
                                                children: currentTable.headers.map((header, index)=>{
                                                    return /*#__PURE__*/ _jsx("th", {
                                                        children: /*#__PURE__*/ _jsxs("button", {
                                                            className: "table-sort-btn ".concat((tableSort === null || tableSort === void 0 ? void 0 : tableSort.columnIndex) === index ? "is-active" : ""),
                                                            type: "button",
                                                            onClick: ()=>toggleTableSort(index),
                                                            children: [
                                                                /*#__PURE__*/ _jsx("span", {
                                                                    children: header
                                                                }),
                                                                /*#__PURE__*/ _jsx("span", {
                                                                    className: "table-sort-btn__icon",
                                                                    children: (tableSort === null || tableSort === void 0 ? void 0 : tableSort.columnIndex) === index ? tableSort.direction === "asc" ? "▲" : "▼" : "↕"
                                                                })
                                                            ]
                                                        })
                                                    }, header);
                                                })
                                            })
                                        }),
                                        /*#__PURE__*/ _jsx("tbody", {
                                            children: currentTable.rows.map((row, index)=>/*#__PURE__*/ _jsx("tr", {
                                                    className: row.isTotal ? "is-total" : "",
                                                    children: row.values.map((value, cellIndex)=>{
                                                        var _currentTable_headers_cellIndex;
                                                        const header = (_currentTable_headers_cellIndex = currentTable.headers[cellIndex]) !== null && _currentTable_headers_cellIndex !== void 0 ? _currentTable_headers_cellIndex : "";
                                                        const planClass = getPlanCellClass(header, value);
                                                        return /*#__PURE__*/ _jsx("td", {
                                                            className: planClass,
                                                            children: value
                                                        }, "".concat(index, "-").concat(cellIndex));
                                                    })
                                                }, "".concat(row.values[0], "-").concat(index)))
                                        })
                                    ]
                                })
                            }),
                            "          ",
                            error ? /*#__PURE__*/ _jsx("div", {
                                className: "error-banner",
                                children: error
                            }) : null
                        ]
                    })
                ]
            })
        ]
    });
}


































