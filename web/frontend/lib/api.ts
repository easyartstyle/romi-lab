export type UserRead = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type ProjectMemberRead = {
  id: number;
  project_id: number;
  user_id: number;
  role: string;
  is_owner: boolean;
  created_at: string;
  email: string | null;
  full_name: string | null;
  system_role: string | null;
};

export type UserInviteResponse = {
  user: UserRead;
  invite_url: string;
  project_id: number | null;
  project_role: string | null;
};

export type AuthResponse = {
  user_id: number;
  email: string;
  full_name: string;
  role: string;
  access_token: string;
  token_type: string;
  issued_at: string;
};





export type InviteInfoResponse = {
  email: string;
  full_name: string;
  role: string;
};

export type ProjectRead = {
  id: number;
  name: string;
  slug: string;
  status: string;
  owner_user_id: number | null;
  created_at: string;
  updated_at: string;
};

export type ProjectPlanRead = {
  id: number;
  project_id: number;
  period_from: string;
  period_to: string;
    product: string;
  source: string;
  type: string;
  budget: number;
  leads: number;
  created_at: string;
  updated_at: string;
};

export type ProjectPlanUpsertRequest = {
  period_from: string;
  period_to: string;
    product?: string;
  source?: string;
  type?: string;
  budget?: number;
  leads?: number;
};

export type DashboardMetricRead = {
  label: string;
  value: string;
};

export type DashboardTableRowRead = {
  values: string[];
  is_total: boolean;
};

export type DashboardFilterOptionRead = {
  key: string;
  label: string;
  options: string[];
};

export type DashboardRecordRead = {
  date: string;
  source: string;
  type: string;
  medium: string;
  campaign: string;
  group_name: string;
  ad_name: string;
  keyword: string;
  region: string;
  device: string;
  placement: string;
  position: string;
  url: string;
  product: string;
  cost: number;
  impressions: number;
  clicks: number;
  cpc: number;
  ctr: number;
  leads: number;
  cpl: number;
  cr1: number;
  sales: number;
  cr2: number;
  avg_check: number;
  revenue: number;
  margin: number;
  romi: number;
};

export type ProjectDashboardRead = {
  project: ProjectRead;
  period_label: string;
  filters: string[];
  metrics: DashboardMetricRead[];
  table_headers: string[];
  table_rows: DashboardTableRowRead[];
  filter_options: DashboardFilterOptionRead[];
  records: DashboardRecordRead[];
};

export type AdsImportRow = {
  date: string;
  source?: string;
  medium?: string;
  campaign?: string;
  group_name?: string;
  ad_name?: string;
  keyword?: string;
  region?: string;
  device?: string;
  placement?: string;
  position?: string;
  url?: string;
  product?: string;
  cost?: number;
  impressions?: number;
  clicks?: number;
};

export type CrmImportRow = {
  date: string;
  source?: string;
  medium?: string;
  campaign?: string;
  group_name?: string;
  ad_name?: string;
  keyword?: string;
  region?: string;
  device?: string;
  placement?: string;
  position?: string;
  url?: string;
  product?: string;
  leads?: number;
  sales?: number;
  revenue?: number;
};

export type ProjectDataImportRequest = {
  replace_existing?: boolean;
  ads_rows: AdsImportRow[];
  crm_rows: CrmImportRow[];
};

export type ProjectDataImportResult = {
  project_id: number;
  ads_rows_imported: number;
  crm_rows_imported: number;
  replace_existing: boolean;
};


export type ProjectConnectionRead = {
  id: number;
  project_id: number;
  category: string;
  platform: string;
  name: string;
  identifier: string;
  api_mode: string;
  client_login_mode: string;
  token: string;
  client_id: string;
  client_secret: string;
  refresh_token: string;
  status: string;
  status_comment: string;
  checked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectConnectionUpsertRequest = {
  category?: string;
  platform?: string;
  name: string;
  identifier?: string;
  api_mode?: string;
  client_login_mode?: string;
  token?: string;
  client_id?: string;
  client_secret?: string;
  refresh_token?: string;
};

export type ProjectConnectionTestResult = {
  ok: boolean;
  status: string;
  status_comment: string;
  checked_at: string | null;
};
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const TOKEN_KEY = "analytics_web_access_token";
const USER_KEY = "analytics_web_user";
const SESSION_EXPIRED_MESSAGE = "РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ.";

export function getApiBase(): string {
  return API_BASE;
}

async function readError(response: Response, fallbackMessage: string): Promise<string> {
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string };
      return payload.detail || fallbackMessage;
    }

    const text = await response.text();
    return text || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

async function ensureAuthorized(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok) {
    return;
  }

  const message = await readError(response, fallbackMessage);
  if (response.status === 401) {
    clearSession();
    throw new Error(SESSION_EXPIRED_MESSAGE);
  }

  throw new Error(message);
}

export async function apiRegister(email: string, password: string, fullName: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°С‚СЊСЃСЏ"));
  }

  return response.json();
}

export async function apiLogin(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РїРѕР»РЅРёС‚СЊ РІС…РѕРґ"));
  }

  return response.json();
}


export async function fetchInviteInfo(token: string): Promise<InviteInfoResponse> {
  const response = await fetch(`${API_BASE}/auth/invite/${token}`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readError(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РєСЂС‹С‚СЊ РїСЂРёРіР»Р°С€РµРЅРёРµ"));
  }

  return response.json();
}

export async function acceptInvite(token: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE}/auth/invite/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });

  if (!response.ok) {
    throw new Error(await readError(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРёРЅСЏС‚СЊ РїСЂРёРіР»Р°С€РµРЅРёРµ"));
  }

  return response.json();
}
export async function fetchMyProjects(token: string): Promise<ProjectRead[]> {
  const response = await fetch(`${API_BASE}/projects/my`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїСЂРѕРµРєС‚С‹");
  return response.json();
}

export async function fetchProjectById(token: string, projectId: number | string): Promise<ProjectRead> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїСЂРѕРµРєС‚");
  return response.json();
}

export async function fetchProjectDashboard(token: string, projectId: number | string): Promise<ProjectDashboardRead> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ СЂР°Р±РѕС‡РёР№ РѕС‚С‡РµС‚");
  return response.json();
}

export async function createProject(token: string, name: string): Promise<ProjectRead> {
  const response = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ РїСЂРѕРµРєС‚");
  return response.json();
}
export async function deleteProject(token: string, projectId: number | string): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РїСЂРѕРµРєС‚");
}

export async function importProjectData(
  token: string,
  projectId: number | string,
  payload: ProjectDataImportRequest,
): Promise<ProjectDataImportResult> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/data/import`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РёРјРїРѕСЂС‚РёСЂРѕРІР°С‚СЊ РґР°РЅРЅС‹Рµ РїСЂРѕРµРєС‚Р°");
  return response.json();
}

export async function fetchProjectPlans(token: string, projectId: number | string): Promise<ProjectPlanRead[]> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/plans`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїР»Р°РЅС‹ РїСЂРѕРµРєС‚Р°");
  return response.json();
}

export async function saveProjectPlan(
  token: string,
  projectId: number | string,
  payload: ProjectPlanUpsertRequest,
): Promise<ProjectPlanRead> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/plans`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РїР»Р°РЅ");
  return response.json();
}

export async function deleteProjectPlan(
  token: string,
  projectId: number | string,
  planId: number,
): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/plans/${planId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РїР»Р°РЅ");
}

export function storeSession(payload: AuthResponse): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(TOKEN_KEY, payload.access_token);
  window.localStorage.setItem(
    USER_KEY,
    JSON.stringify({
      id: payload.user_id,
      email: payload.email,
      full_name: payload.full_name,
      role: payload.role,
      issued_at: payload.issued_at,
    }),
  );
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser():
  | {
      id: number;
      email: string;
      full_name: string;
      role: string;
      issued_at: string;
    }
  | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as {
      id: number;
      email: string;
      full_name: string;
      role: string;
      issued_at: string;
    };
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export async function fetchProjectConnections(token: string, projectId: number | string, category = "ads"): Promise<ProjectConnectionRead[]> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/connections?category=${category}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїРѕРґРєР»СЋС‡РµРЅРёСЏ РїСЂРѕРµРєС‚Р°");
  return response.json();
}

export async function saveProjectConnection(
  token: string,
  projectId: number | string,
  payload: ProjectConnectionUpsertRequest,
  connectionId?: number,
): Promise<ProjectConnectionRead> {
  const url = connectionId
    ? `${API_BASE}/projects/${projectId}/connections?connection_id=${connectionId}`
    : `${API_BASE}/projects/${projectId}/connections`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РїРѕРґРєР»СЋС‡РµРЅРёРµ");
  return response.json();
}

export async function testProjectConnection(
  token: string,
  projectId: number | string,
  connectionId: number,
): Promise<ProjectConnectionTestResult> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/connections/${connectionId}/test`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРІРµСЂРёС‚СЊ РїРѕРґРєР»СЋС‡РµРЅРёРµ");
  return response.json();
}

export async function deleteProjectConnection(
  token: string,
  projectId: number | string,
  connectionId: number,
): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/connections/${connectionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РїРѕРґРєР»СЋС‡РµРЅРёРµ");
}



export async function fetchUsers(token: string): Promise<UserRead[]> {
  const response = await fetch(`${API_BASE}/users`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№");
  return response.json();
}

export async function updateUser(
  token: string,
  userId: number,
  payload: { role: string; is_active?: boolean },
): Promise<UserRead> {
  const response = await fetch(`${API_BASE}/users/${userId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ");
  return response.json();
}
export async function deleteUser(token: string, userId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/users/${userId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ");
}

export async function fetchProjectMembers(
  token: string,
  projectId: number | string,
): Promise<ProjectMemberRead[]> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/members`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ РґРѕСЃС‚СѓРїС‹ РїСЂРѕРµРєС‚Р°");
  return response.json();
}

export async function assignProjectMember(
  token: string,
  projectId: number | string,
  payload: { email: string; role: string },
): Promise<ProjectMemberRead> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/members`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РІС‹РґР°С‚СЊ РґРѕСЃС‚СѓРї Рє РїСЂРѕРµРєС‚Сѓ");
  return response.json();
}

export async function updateProjectMember(
  token: string,
  projectId: number | string,
  memberId: number,
  payload: { role: string },
): Promise<ProjectMemberRead> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/members/${memberId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ СЂРѕР»СЊ РІ РїСЂРѕРµРєС‚Рµ");
  return response.json();
}

export async function deleteProjectMember(
  token: string,
  projectId: number | string,
  memberId: number,
): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/members/${memberId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РґРѕСЃС‚СѓРї Рє РїСЂРѕРµРєС‚Сѓ");
}



export async function inviteUser(
  token: string,
  payload: { email: string; full_name: string; role: string; project_id?: number | null; project_role?: string | null },
): Promise<UserInviteResponse> {
  const response = await fetch(`${API_BASE}/users/invite`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  await ensureAuthorized(response, "РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРёРіР»Р°СЃРёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ");
  return response.json();
}


