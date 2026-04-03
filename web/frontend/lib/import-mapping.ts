export type ImportTarget = "ads" | "crm";

export type ImportFieldDefinition = {
  key: string;
  label: string;
  required?: boolean;
};

export const ADS_IMPORT_FIELDS: ImportFieldDefinition[] = [
  { key: "date", label: "Дата", required: true },
  { key: "source", label: "Источник" },
  { key: "medium", label: "Тип" },
  { key: "campaign", label: "Кампания" },
  { key: "group_name", label: "Группа" },
  { key: "ad_name", label: "Объявление" },
  { key: "keyword", label: "Ключевая фраза" },
  { key: "region", label: "Регион" },
  { key: "device", label: "Устройство" },
  { key: "placement", label: "Площадка" },
  { key: "position", label: "Position" },
  { key: "url", label: "URL" },
  { key: "product", label: "Продукт" },
  { key: "cost", label: "Расход" },
  { key: "impressions", label: "Показы" },
  { key: "clicks", label: "Клики" },
];

export const CRM_IMPORT_FIELDS: ImportFieldDefinition[] = [
  { key: "date", label: "Дата", required: true },
  { key: "source", label: "Источник" },
  { key: "medium", label: "Тип" },
  { key: "campaign", label: "Кампания" },
  { key: "group_name", label: "Группа" },
  { key: "ad_name", label: "Объявление" },
  { key: "keyword", label: "Ключевая фраза" },
  { key: "region", label: "Регион" },
  { key: "device", label: "Устройство" },
  { key: "placement", label: "Площадка" },
  { key: "position", label: "Position" },
  { key: "url", label: "URL" },
  { key: "product", label: "Продукт" },
  { key: "leads", label: "Лиды" },
  { key: "sales", label: "Продажи" },
  { key: "revenue", label: "Выручка" },
];

const MOJIBAKE_HEADER_MAP: Record<string, string> = {
  "Р”Р°С‚Р°": "Дата",
  "РљР°РјРїР°РЅРёСЏ": "Кампания",
  "Р“СЂСѓРїРїР°": "Группа",
  "РћР±СЉСЏРІР»РµРЅРёРµ": "Объявление",
  "Р Р°СЃС…РѕРґ": "Расход",
  "РџРѕРєР°Р·С‹": "Показы",
  "Р РѕРєР°Р·С‹": "Показы",
  "Р РѕРєР°Р·С‹ ": "Показы",
  "РљР»РёРєРё": "Клики",
  "Р›РёРґС‹": "Лиды",
  "РџСЂРѕРґР°Р¶Рё": "Продажи",
  "Р’С‹СЂСѓС‡РєР°": "Выручка",
  "РЎСЂ.С‡РµРє": "Ср.чек",
  "РСЃС‚РѕС‡РЅРёРє": "Источник",
  "РўРёРї": "Тип",
  "РљР»СЋС‡РµРІР°СЏС„СЂР°Р·Р°": "Ключевая фраза",
  "Р РµРіРёРѕРЅ": "Регион",
  "РЈСЃС‚СЂРѕР№СЃС‚РІРѕ": "Устройство",
  "РџР»РѕС‰Р°РґРєР°": "Площадка",
};

const ADS_ALIASES: Record<string, string[]> = {
  date: ["date", "дата"],
  source: ["utm_source", "источник", "source_name"],
  medium: ["utm_medium", "тип", "medium_name"],
  campaign: ["utm_campaign", "campaign", "campaign_id", "{{campaign_id}}", "кампания"],
  group_name: ["group", "groupname", "gbid", "{gbid}", "adgroup", "ad_group", "группа"],
  ad_name: ["ad", "adname", "content", "ad_id", "{ad_id}", "adid", "объявление"],
  keyword: ["keyword", "term", "utm_term", "ключеваяфраза"],
  region: ["region", "regionname", "region_name", "{region_name}", "регион"],
  device: ["device", "devicetype", "device_type", "{device_type}", "устройство"],
  placement: ["placement", "site", "{source}", "source", "площадка"],
  position: ["position", "{position}"],
  url: ["url", "link", "finalurl", "landingpage", "ссылка"],
  product: ["product", "sku", "item", "продукт"],
  cost: ["cost", "spend", "расход"],
  impressions: ["impressions", "показы"],
  clicks: ["clicks", "клики"],
};

function decodeByteString(value: string, encoding: string) {
  const bytes = Uint8Array.from(Array.from(value).map((char) => char.charCodeAt(0) & 0xff));
  return new TextDecoder(encoding as any).decode(bytes);
}

const CP1251_REVERSE_MAP = (() => {
  const decoded = new TextDecoder('windows-1251' as any).decode(Uint8Array.from({ length: 256 }, (_, index) => index));
  const reverse = new Map<string, number>();
  for (let index = 0; index < decoded.length; index += 1) {
    reverse.set(decoded[index], index);
  }
  return reverse;
})();

function decodeCp1251Mojibake(value: string) {
  const bytes = Uint8Array.from(Array.from(value).map((char) => CP1251_REVERSE_MAP.get(char) ?? (char.charCodeAt(0) & 0xff)));
  return new TextDecoder('utf-8' as any).decode(bytes);
}

function scoreReadableText(value: string) {
  const cyrillic = value.match(/[А-Яа-яЁё]/g)?.length ?? 0;
  const latinOrDigits = value.match(/[A-Za-z0-9]/g)?.length ?? 0;
  const mojibake = value.match(/[ÐÑÃÍÂÊËÎÓ]/g)?.length ?? 0;
  const brokenPairs = value.match(/[РС][^А-Яа-яЁё\s]/g)?.length ?? 0;
  return cyrillic * 6 + latinOrDigits - mojibake * 4 - brokenPairs * 5;
}

function shouldTryRepair(text: string) {
  if (!text) return false;
  if (MOJIBAKE_HEADER_MAP[text]) return true;
  return /[ÐÑÃÍÂÊËÎÓ]/.test(text) || /Р./.test(text) || /С./.test(text);
}

export function repairImportText(value: unknown) {
  const text = String(value ?? '').trim();
  if (!text) return '';
  if (MOJIBAKE_HEADER_MAP[text]) return MOJIBAKE_HEADER_MAP[text];
  const looksHealthyCyrillic = /[А-Яа-яЁё]/.test(text) && !shouldTryRepair(text);
  if (looksHealthyCyrillic) return text;
  if (!shouldTryRepair(text)) return text;
  const candidates = new Set<string>([text]);
  const attempts = [text];
  for (const attempt of attempts) {
    try { candidates.add(decodeByteString(attempt, 'utf-8')); } catch {}
    try { candidates.add(decodeByteString(attempt, 'windows-1251')); } catch {}
    try { candidates.add(decodeCp1251Mojibake(attempt)); } catch {}
  }
  const expanded = Array.from(candidates);
  for (const candidate of expanded) {
    if (candidate !== text && shouldTryRepair(candidate)) {
      try { candidates.add(decodeCp1251Mojibake(candidate)); } catch {}
      try { candidates.add(decodeByteString(candidate, 'utf-8')); } catch {}
    }
  }
  return Array.from(candidates)
    .map((candidate) => MOJIBAKE_HEADER_MAP[candidate] ?? candidate)
    .sort((a, b) => scoreReadableText(b) - scoreReadableText(a))[0] ?? text;
}

function toTextValue(value: unknown, fallback: string) {
  const repaired = repairImportText(value).trim();
  return repaired || fallback;
}

const CRM_ALIASES: Record<string, string[]> = {
  date: ["date", "дата"],
  source: ["utm_source", "source", "источник"],
  medium: ["utm_medium", "medium", "тип"],
  campaign: ["utm_campaign", "campaign", "campaign_id", "{{campaign_id}}", "кампания"],
  group_name: ["group", "groupname", "gbid", "{gbid}", "группа"],
  ad_name: ["ad", "adname", "content", "ad_id", "{ad_id}", "объявление"],
  keyword: ["keyword", "term", "utm_term", "ключеваяфраза"],
  region: ["region", "regionname", "region_name", "{region_name}", "регион"],
  device: ["device", "devicetype", "device_type", "{device_type}", "устройство"],
  placement: ["placement", "site", "{source}", "source", "площадка"],
  position: ["position", "{position}"],
  url: ["url", "link", "finalurl", "landingpage", "ссылка"],
  product: ["product", "sku", "item", "продукт"],
  leads: ["leads", "лиды"],
  sales: ["sales", "продажи"],
  revenue: ["revenue", "amount", "выручка"],
};

function normalizeHeader(value: string) {
  return repairImportText(value)
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^a-zа-я0-9{}]/g, "");
}

export function getImportFields(target: ImportTarget) {
  return target === "ads" ? ADS_IMPORT_FIELDS : CRM_IMPORT_FIELDS;
}

export function inferImportMapping(columns: string[], target: ImportTarget) {
  const aliases = target === "ads" ? ADS_ALIASES : CRM_ALIASES;
  const normalizedColumns = columns.map((column) => ({
    column,
    normalized: normalizeHeader(column),
  }));
  return getImportFields(target).reduce<Record<string, string>>((accumulator, field) => {
    const match = normalizedColumns.find(({ normalized }) =>
      (aliases[field.key] ?? []).map(normalizeHeader).includes(normalized),
    );
    accumulator[field.key] = match?.column ?? "";
    return accumulator;
  }, {});
}

function getCellByMapping(row: Record<string, unknown>, fieldKey: string, target: ImportTarget, mapping: Record<string, string>) {
  const selectedColumn = mapping[fieldKey];
  if (selectedColumn && Object.prototype.hasOwnProperty.call(row, selectedColumn)) {
    return row[selectedColumn];
  }
  const aliases = (target === "ads" ? ADS_ALIASES : CRM_ALIASES)[fieldKey] ?? [];
  const aliasSet = new Set(aliases.map(normalizeHeader));
  for (const [key, value] of Object.entries(row)) {
    if (aliasSet.has(normalizeHeader(key))) return value;
  }
  return undefined;
}

function toNumber(value: unknown) {
  if (typeof value === "number") return value;
  const normalized = repairImportText(value).replace(/\s/g, "").replace(/,/g, ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(date: Date) {
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const yyyy = date.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

function parseDateValue(value: unknown) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return formatDate(value);
  const text = repairImportText(value).trim();
  if (!text) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(text)) return formatDate(new Date(`${text.slice(0, 10)}T00:00:00`));
  if (/^\d{2}\.\d{2}\.\d{2,4}$/.test(text)) {
    const [d, m, y0] = text.split(".");
    const y = y0.length === 2 ? `20${y0}` : y0;
    return `${d}.${m}.${y}`;
  }
  return text;
}

export function remapImportedRows(rows: Record<string, unknown>[], target: ImportTarget, mapping: Record<string, string>) {
  return rows
    .map((row) => {
      const date = parseDateValue(getCellByMapping(row, "date", target, mapping));
      if (!date) return null;
      if (target === "ads") {
        return {
          date,
          source: toTextValue(getCellByMapping(row, "source", target, mapping), "Не указано"),
          medium: toTextValue(getCellByMapping(row, "medium", target, mapping), "Не указано"),
          campaign: toTextValue(getCellByMapping(row, "campaign", target, mapping), "(Не указано)"),
          group_name: toTextValue(getCellByMapping(row, "group_name", target, mapping), "(Не указано)"),
          ad_name: toTextValue(getCellByMapping(row, "ad_name", target, mapping), "(Не указано)"),
          keyword: toTextValue(getCellByMapping(row, "keyword", target, mapping), "(Не указано)"),
          region: toTextValue(getCellByMapping(row, "region", target, mapping), "(Не указано)"),
          device: toTextValue(getCellByMapping(row, "device", target, mapping), "(Не указано)"),
          placement: toTextValue(getCellByMapping(row, "placement", target, mapping), "(Не указано)"),
          position: toTextValue(getCellByMapping(row, "position", target, mapping), "(Не указано)"),
          url: toTextValue(getCellByMapping(row, "url", target, mapping), "(Не указано)"),
          product: toTextValue(getCellByMapping(row, "product", target, mapping), "(Не указано)"),
          cost: toNumber(getCellByMapping(row, "cost", target, mapping)),
          impressions: Math.round(toNumber(getCellByMapping(row, "impressions", target, mapping))),
          clicks: Math.round(toNumber(getCellByMapping(row, "clicks", target, mapping))),
        };
      }
      return {
        date,
        source: toTextValue(getCellByMapping(row, "source", target, mapping), "Не указано"),
        medium: toTextValue(getCellByMapping(row, "medium", target, mapping), "Не указано"),
        campaign: toTextValue(getCellByMapping(row, "campaign", target, mapping), "(Не указано)"),
        group_name: toTextValue(getCellByMapping(row, "group_name", target, mapping), "(Не указано)"),
        ad_name: toTextValue(getCellByMapping(row, "ad_name", target, mapping), "(Не указано)"),
        keyword: toTextValue(getCellByMapping(row, "keyword", target, mapping), "(Не указано)"),
        region: toTextValue(getCellByMapping(row, "region", target, mapping), "(Не указано)"),
        device: toTextValue(getCellByMapping(row, "device", target, mapping), "(Не указано)"),
        placement: toTextValue(getCellByMapping(row, "placement", target, mapping), "(Не указано)"),
        position: toTextValue(getCellByMapping(row, "position", target, mapping), "(Не указано)"),
        url: toTextValue(getCellByMapping(row, "url", target, mapping), "(Не указано)"),
        product: toTextValue(getCellByMapping(row, "product", target, mapping), "(Не указано)"),
        leads: Math.round(toNumber(getCellByMapping(row, "leads", target, mapping))),
        sales: Math.round(toNumber(getCellByMapping(row, "sales", target, mapping))),
        revenue: toNumber(getCellByMapping(row, "revenue", target, mapping)),
      };
    })
    .filter(Boolean);
}

