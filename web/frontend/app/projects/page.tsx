"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  clearSession,
  createProject,
  deleteProject,
  fetchMyProjects,
  fetchProjectDashboard,
  getStoredToken,
  getStoredUser,
  type DashboardRecordRead,
  type ProjectDashboardRead,
  type ProjectRead,
} from "@/lib/api";

function parseDashboardDate(value: string): number | null {
  if (!value) return null;

  const parts = value.split(".");
  if (parts.length === 3) {
    const [day, month, year] = parts.map(Number);
    const date = new Date(year, month - 1, day);
    return Number.isNaN(date.getTime()) ? null : date.getTime();
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.getTime();
}

function formatInt(value: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(value || 0));
}

function formatDecimal(value: number): string {
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function formatPercent(value: number): string {
  return `${formatDecimal(value)}%`;
}

function buildSevenDayMetrics(dashboard: ProjectDashboardRead | null) {
  if (!dashboard?.records?.length) return [];

  const datedRecords = dashboard.records
    .map((record) => ({ record, ts: parseDashboardDate(record.date) }))
    .filter((item): item is { record: DashboardRecordRead; ts: number } => item.ts !== null);

  if (!datedRecords.length) return [];

  const maxTs = Math.max(...datedRecords.map((item) => item.ts));
  const minTs = maxTs - 6 * 24 * 60 * 60 * 1000;
  const records = datedRecords.filter((item) => item.ts >= minTs && item.ts <= maxTs).map((item) => item.record);

  const totals = records.reduce(
    (acc, record) => {
      acc.cost += Number(record.cost || 0);
      acc.impressions += Number(record.impressions || 0);
      acc.clicks += Number(record.clicks || 0);
      acc.leads += Number(record.leads || 0);
      acc.sales += Number(record.sales || 0);
      acc.revenue += Number(record.revenue || 0);
      return acc;
    },
    { cost: 0, impressions: 0, clicks: 0, leads: 0, sales: 0, revenue: 0 },
  );

  const cpc = totals.clicks > 0 ? totals.cost / totals.clicks : 0;
  const ctr = totals.impressions > 0 ? (totals.clicks / totals.impressions) * 100 : 0;
  const cpl = totals.leads > 0 ? totals.cost / totals.leads : 0;
  const cr1 = totals.clicks > 0 ? (totals.leads / totals.clicks) * 100 : 0;
  const cr2 = totals.leads > 0 ? (totals.sales / totals.leads) * 100 : 0;
  const avgCheck = totals.sales > 0 ? totals.revenue / totals.sales : 0;
  const margin = totals.revenue - totals.cost;
  const romi = totals.cost > 0 ? (margin / totals.cost) * 100 : totals.revenue > 0 ? 100 : -100;

  return [
    { label: "Расход", value: formatInt(totals.cost) },
    { label: "Показы", value: formatInt(totals.impressions) },
    { label: "Клики", value: formatInt(totals.clicks) },
    { label: "CPC", value: formatInt(cpc) },
    { label: "CTR", value: formatPercent(ctr) },
    { label: "Лиды", value: formatInt(totals.leads) },
    { label: "CPL", value: formatInt(cpl) },
    { label: "CR1", value: formatDecimal(cr1) },
    { label: "Продажи", value: formatInt(totals.sales) },
    { label: "CR2", value: formatDecimal(cr2) },
    { label: "Ср.чек", value: formatInt(avgCheck) },
    { label: "Выручка", value: formatInt(totals.revenue) },
    { label: "Маржа", value: formatInt(margin) },
    { label: "ROMI", value: formatPercent(romi) },
  ];
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);
  const [activeDashboard, setActiveDashboard] = useState<ProjectDashboardRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadProjects() {
      const token = getStoredToken();
      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const result = await fetchMyProjects(token);
        setProjects(result);
        if (result.length > 0) {
          setActiveProjectId(result[0].id);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Не удалось загрузить проекты";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    void loadProjects();
  }, [router]);

  useEffect(() => {
    async function loadDashboard() {
      const token = getStoredToken();
      if (!token || !activeProjectId) {
        setActiveDashboard(null);
        return;
      }

      setDashboardLoading(true);
      try {
        const result = await fetchProjectDashboard(token, activeProjectId);
        setActiveDashboard(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Не удалось загрузить проект";
        setError(message);
      } finally {
        setDashboardLoading(false);
      }
    }

    void loadDashboard();
  }, [activeProjectId, router]);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    if (!newProjectName.trim()) {
      setError("Введите название проекта");
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const project = await createProject(token, newProjectName.trim());
      setProjects((prev) => [project, ...prev]);
      setActiveProjectId(project.id);
      setNewProjectName("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось создать проект";
      setError(message);
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteProject() {
    const token = getStoredToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    if (!activeProject) {
      setError("Сначала выберите проект");
      return;
    }

    if (!window.confirm(`Удалить проект "${activeProject.name}"?`)) {
      return;
    }

    setDeleting(true);
    setError(null);

    try {
      await deleteProject(token, activeProject.id);
      const nextProjects = projects.filter((project) => project.id !== activeProject.id);
      setProjects(nextProjects);
      setActiveProjectId(nextProjects[0]?.id ?? null);
      setActiveDashboard(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось удалить проект";
      setError(message);
    } finally {
      setDeleting(false);
    }
  }

  const currentUser = useMemo(() => getStoredUser(), []);
  const canManageProjects = currentUser?.role === "admin" || currentUser?.role === "manager";
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? projects[0] ?? null;
  const quickMetrics = useMemo(() => buildSevenDayMetrics(activeDashboard), [activeDashboard]);

  return (
    <main className="page-wrap">
      <div className="projects-layout">
        <aside className="sidebar-card">
          <div>
            <div className="section-title">Мои проекты</div>
            <div className="project-list">
              {loading ? <div className="project-chip">Загрузка...</div> : null}
              {!loading && projects.length === 0 ? <div className="project-chip">Проектов пока нет</div> : null}
              {projects.map((project) => (
                <button
                  className={project.id === activeProjectId ? "project-chip active" : "project-chip"}
                  key={project.id}
                  onClick={() => setActiveProjectId(project.id)}
                  type="button"
                >
                  {project.name}
                </button>
              ))}
            </div>
          </div>

          <div className="mini-input">Пользователь: {currentUser?.full_name ?? "—"}</div>

          <form className="form-grid" onSubmit={handleCreateProject}>
            <input
              placeholder="Название нового проекта"
              type="text"
              value={newProjectName}
              onChange={(event) => setNewProjectName(event.target.value)}
            />
            <button className="secondary-btn" disabled={creating} type="submit">
              {creating ? "Создаем..." : "Создать проект"}
            </button>
          </form>

          <div className="actions-row">
            <button
              className="primary-btn"
              type="button"
              onClick={() => {
                if (activeProject) {
                  router.push(`/projects/${activeProject.id}`);
                }
              }}
              disabled={!activeProject}
            >
              Открыть рабочий отчет
            </button>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => void handleDeleteProject()}
              disabled={!activeProject || deleting}
            >
              {deleting ? "Удаляем..." : "Удалить проект"}
            </button>
            <button
              className="ghost-btn"
              type="button"
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
            >
              Выйти
            </button>
          </div>
        </aside>

        <section className="content-card">
          <div className="section-title">{activeProject?.name ?? "Проекты"}</div>
          {error ? <div className="error-banner">{error}</div> : null}

          {activeProject ? (
            <>
              <div className="mini-input" style={{ marginBottom: 16 }}>
                В краткой сводке проекта ниже показаны данные за последние 7 дней. Полный интерактивный отчет с
                фильтрами, вкладками и таблицей открывается по кнопке «Открыть рабочий отчет».
              </div>

              <div className="kpi-row">
                {dashboardLoading ? (
                  <div className="project-chip">Загружаем сводку проекта...</div>
                ) : quickMetrics.length > 0 ? (
                  quickMetrics.map((metric) => (
                    <div className="metric-card" key={metric.label}>
                      <div className="label">{metric.label}</div>
                      <div className="value">{metric.value}</div>
                    </div>
                  ))
                ) : (
                  <div className="project-chip">В проекте пока нет данных за последние 7 дней</div>
                )}
              </div>
            </>
          ) : (
            <div className="mini-input">Выберите проект слева или создайте новый.</div>
          )}
        </section>
      </div>
    </main>
  );
}
