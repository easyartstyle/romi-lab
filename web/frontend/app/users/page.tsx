"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  assignProjectMember,
  clearSession,
  deleteProjectMember,
  deleteUser,
  fetchMyProjects,
  fetchProjectMembers,
  fetchUsers,
  getStoredToken,
  getStoredUser,
  inviteUser,
  updateProjectMember,
  updateUser,
  type ProjectMemberRead,
  type ProjectRead,
  type UserRead,
} from "@/lib/api";

const SYSTEM_ROLES = [
  { key: "admin", label: "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440" },
  { key: "manager", label: "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440" },
  { key: "client", label: "\u041a\u043b\u0438\u0435\u043d\u0442" },
] as const;

const PROJECT_ROLES = [
  { key: "owner", label: "\u0412\u043b\u0430\u0434\u0435\u043b\u0435\u0446" },
  { key: "editor", label: "\u0420\u0435\u0434\u0430\u043a\u0442\u043e\u0440" },
  { key: "viewer", label: "\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440" },
  { key: "client", label: "\u041a\u043b\u0438\u0435\u043d\u0442" },
] as const;

const PRIMARY_OWNER_EMAIL = "easyartstyle@gmail.com";

function getSystemRoleLabel(role: string): string {
  return SYSTEM_ROLES.find((item) => item.key === role)?.label ?? role;
}

function getProjectRoleLabel(role: string): string {
  return PROJECT_ROLES.find((item) => item.key === role)?.label ?? role;
}

function buildInviteMessage(inviteUrl: string, fullName: string, projectName?: string | null): string {
  const projectLine = projectName ? "\n\u041f\u0440\u043e\u0435\u043a\u0442: " + projectName : "";
  return "\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435, " + fullName + ".\n\u0412\u0430\u0441 \u043f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u043b\u0438 \u0432 \u0432\u0435\u0431-\u043a\u0430\u0431\u0438\u043d\u0435\u0442 \u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0438." + projectLine + "\n\n\u0421\u0441\u044b\u043b\u043a\u0430-\u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435: " + inviteUrl + "\n\n\u041f\u043e \u044d\u0442\u043e\u0439 \u0441\u0441\u044b\u043b\u043a\u0435 \u0432\u044b \u0441\u043c\u043e\u0436\u0435\u0442\u0435 \u0437\u0430\u0434\u0430\u0442\u044c \u043f\u0430\u0440\u043e\u043b\u044c \u0438 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044e.";
}

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserRead[]>([]);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [members, setMembers] = useState<ProjectMemberRead[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [userRole, setUserRole] = useState("client");
  const [userActive, setUserActive] = useState(true);
  const [memberRole, setMemberRole] = useState("viewer");
  const [userSearch, setUserSearch] = useState("");
  const [onlyWithoutAccess, setOnlyWithoutAccess] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFullName, setInviteFullName] = useState("");
  const [inviteRole, setInviteRole] = useState("client");
  const [inviteProjectId, setInviteProjectId] = useState<number | null>(null);
  const [inviteProjectRole, setInviteProjectRole] = useState("client");
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [inviteCopied, setInviteCopied] = useState(false);
  const [inviteMessageCopied, setInviteMessageCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [savingUser, setSavingUser] = useState(false);
  const [deletingUser, setDeletingUser] = useState(false);
  const [savingAccess, setSavingAccess] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const currentUser = useMemo(() => getStoredUser(), []);
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const inviteProject = projects.find((project) => project.id === inviteProjectId) ?? null;
  const memberUserIds = useMemo(() => new Set(members.map((item) => item.user_id)), [members]);
  const canAssignOwner = (currentUser?.email ?? "").toLowerCase() === PRIMARY_OWNER_EMAIL;

  const visibleUsers = useMemo(() => {
    const query = userSearch.trim().toLowerCase();
    return users.filter((user) => {
      const matchesSearch = !query || user.full_name.toLowerCase().includes(query) || user.email.toLowerCase().includes(query);
      const matchesAccess = !onlyWithoutAccess || !memberUserIds.has(user.id);
      return matchesSearch && matchesAccess;
    });
  }, [users, userSearch, onlyWithoutAccess, memberUserIds]);

  const selectedUser = visibleUsers.find((user) => user.id === selectedUserId) ?? users.find((user) => user.id === selectedUserId) ?? null;
  const selectedMembership = members.find((item) => item.user_id === selectedUserId) ?? null;

  useEffect(() => {
    async function loadData() {
      const token = getStoredToken();
      const user = getStoredUser();
      if (!token) {
        router.replace("/login");
        return;
      }
      if (user?.role !== "admin") {
        router.replace("/projects");
        return;
      }
      try {
        setError(null);
        const [usersResult, projectsResult] = await Promise.all([fetchUsers(token), fetchMyProjects(token)]);
        setUsers(usersResult);
        setProjects(projectsResult);
        setSelectedUserId(usersResult[0]?.id ?? null);
        setSelectedProjectId(projectsResult[0]?.id ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439");
      } finally {
        setLoading(false);
      }
    }
    void loadData();
  }, [router]);

  useEffect(() => {
    if (!selectedUser) return;
    setUserRole(selectedUser.role);
    setUserActive(selectedUser.is_active);
  }, [selectedUser]);

  useEffect(() => {
    setMemberRole(selectedMembership ? selectedMembership.role : "viewer");
  }, [selectedMembership]);

  useEffect(() => {
    if (!selectedUserId && visibleUsers.length > 0) {
      setSelectedUserId(visibleUsers[0].id);
    }
    if (selectedUserId && visibleUsers.length > 0 && !visibleUsers.some((user) => user.id === selectedUserId)) {
      setSelectedUserId(visibleUsers[0].id);
    }
  }, [visibleUsers, selectedUserId]);

  useEffect(() => {
    async function loadMembers() {
      const token = getStoredToken();
      if (!token || !selectedProjectId) {
        setMembers([]);
        return;
      }
      try {
        setMembersLoading(true);
        setError(null);
        const result = await fetchProjectMembers(token, selectedProjectId);
        setMembers(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u044b \u043f\u0440\u043e\u0435\u043a\u0442\u0430");
      } finally {
        setMembersLoading(false);
      }
    }
    void loadMembers();
  }, [selectedProjectId]);

  async function handleInviteUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    try {
      setInviting(true);
      setError(null);
      setSuccess(null);
      setInviteUrl(null);
      setInviteCopied(false);
      setInviteMessageCopied(false);
      const result = await inviteUser(token, {
        email: inviteEmail,
        full_name: inviteFullName,
        role: inviteRole,
        project_id: inviteProjectId,
        project_role: inviteProjectId ? inviteProjectRole : null,
      });
      setUsers((current) => [...current, result.user].sort((a, b) => a.full_name.localeCompare(b.full_name, "ru")));
      setSelectedUserId(result.user.id);
      setInviteUrl(result.invite_url);
      setInviteEmail("");
      setInviteFullName("");
      setInviteRole("client");
      setInviteProjectId(null);
      setInviteProjectRole("client");
      setSuccess("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u0441\u043e\u0437\u0434\u0430\u043d. \u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439 \u0441\u0441\u044b\u043b\u043a\u0443-\u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435 \u0438 \u043e\u0442\u043f\u0440\u0430\u0432\u044c \u0435\u0435 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044e.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f");
    } finally {
      setInviting(false);
    }
  }

  async function handleCopyInviteLink() {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setInviteCopied(true);
      setSuccess("\u0421\u0441\u044b\u043b\u043a\u0430-\u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435 \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0430.");
    } catch {
      setError("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443.");
    }
  }

  async function handleCopyInviteMessage() {
    if (!inviteUrl) return;
    try {
      const message = buildInviteMessage(inviteUrl, inviteFullName || "\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c", inviteProject?.name ?? null);
      await navigator.clipboard.writeText(message);
      setInviteMessageCopied(true);
      setSuccess("\u0422\u0435\u043a\u0441\u0442 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d.");
    } catch {
      setError("\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f.");
    }
  }

  async function handleSaveUser() {
    const token = getStoredToken();
    if (!token || !selectedUser) return;
    try {
      setSavingUser(true);
      setError(null);
      setSuccess(null);
      const updated = await updateUser(token, selectedUser.id, { role: userRole, is_active: userActive });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSuccess("\u0420\u043e\u043b\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0430.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f");
    } finally {
      setSavingUser(false);
    }
  }

  async function handleDeleteUser() {
    const token = getStoredToken();
    if (!token || !selectedUser) return;
    if (!window.confirm(`\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u00ab${selectedUser.full_name}\u00bb?`)) return;
    try {
      setDeletingUser(true);
      setError(null);
      setSuccess(null);
      await deleteUser(token, selectedUser.id);
      setUsers((current) => {
        const nextUsers = current.filter((item) => item.id !== selectedUser.id);
        setSelectedUserId(nextUsers[0]?.id ?? null);
        return nextUsers;
      });
      setMembers((current) => current.filter((item) => item.user_id !== selectedUser.id));
      setSuccess("\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u0443\u0434\u0430\u043b\u0435\u043d.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f");
    } finally {
      setDeletingUser(false);
    }
  }

  async function handleSaveAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token || !selectedUser || !selectedProject) return;
    try {
      setSavingAccess(true);
      setError(null);
      setSuccess(null);
      if (selectedMembership) {
        await updateProjectMember(token, selectedProject.id, selectedMembership.id, { role: memberRole });
      } else {
        await assignProjectMember(token, selectedProject.id, { email: selectedUser.email, role: memberRole });
      }
      const nextMembers = await fetchProjectMembers(token, selectedProject.id);
      setMembers(nextMembers);
      setSuccess("\u0414\u043e\u0441\u0442\u0443\u043f \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f");
    } finally {
      setSavingAccess(false);
    }
  }

  async function handleRemoveAccess() {
    const token = getStoredToken();
    if (!token || !selectedProject || !selectedMembership) return;
    if (!window.confirm("\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u043a \u044d\u0442\u043e\u043c\u0443 \u043f\u0440\u043e\u0435\u043a\u0442\u0443?")) return;
    try {
      setSavingAccess(true);
      setError(null);
      setSuccess(null);
      await deleteProjectMember(token, selectedProject.id, selectedMembership.id);
      setMembers((current) => current.filter((item) => item.id !== selectedMembership.id));
      setSuccess("\u0414\u043e\u0441\u0442\u0443\u043f \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443 \u0443\u0434\u0430\u043b\u0435\u043d.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f");
    } finally {
      setSavingAccess(false);
    }
  }

  if (loading) {
    return <main className="page-wrap">{"\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439..."}</main>;
  }

  return (
    <main className="page-wrap">
      <div className="projects-layout users-layout">
        <aside className="sidebar-card users-sidebar">
          <div className="users-sidebar__header">
            <Link className="ghost-btn" href="/projects">{"\u041d\u0430\u0437\u0430\u0434"}</Link>
            <button
              className="ghost-btn"
              type="button"
              onClick={() => {
                clearSession();
                router.push("/login");
              }}
            >
              {"\u0412\u044b\u0439\u0442\u0438"}
            </button>
          </div>

          <form className="sidebar-section users-invite-card" onSubmit={handleInviteUser}>
            <div className="section-title">{"\u041f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f"}</div>
            <input className="desktop-input" placeholder="Email" type="email" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} />
            <input className="desktop-input" placeholder={"\u0418\u043c\u044f \u0438 \u0444\u0430\u043c\u0438\u043b\u0438\u044f"} type="text" value={inviteFullName} onChange={(event) => setInviteFullName(event.target.value)} />
            <select className="desktop-input" value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
              {SYSTEM_ROLES.map((role) => (
                <option key={role.key} value={role.key}>{role.label}</option>
              ))}
            </select>
            <select className="desktop-input" value={inviteProjectId ?? ""} onChange={(event) => setInviteProjectId(event.target.value ? Number(event.target.value) : null)}>
              <option value="">{"\u0411\u0435\u0437 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443"}</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
            {inviteProjectId ? (
              <select className="desktop-input" value={inviteProjectRole} onChange={(event) => setInviteProjectRole(event.target.value)}>
                {PROJECT_ROLES.map((role) => (
                  <option key={role.key} value={role.key} disabled={role.key === "owner" && !canAssignOwner}>{role.label}</option>
                ))}
              </select>
            ) : null}
            <button className="primary-btn" type="submit" disabled={inviting}>{inviting ? "\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0430\u0435\u043c..." : "\u041f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c"}</button>
            {inviteUrl ? (
              <div className="mini-input users-temp-password">
                <div className="users-invite-result__title">{"\u0421\u0441\u044b\u043b\u043a\u0430-\u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435"}</div>
                <a href={inviteUrl} target="_blank" rel="noreferrer">{inviteUrl}</a>
                {inviteProject ? <div className="import-subtitle">{"\u041f\u0440\u043e\u0435\u043a\u0442: " + inviteProject.name + " \u2022 \u0420\u043e\u043b\u044c: " + getProjectRoleLabel(inviteProjectRole)}</div> : null}
                <div className="actions-row" style={{ marginTop: 10 }}>
                  <a className="ghost-btn" href={inviteUrl} target="_blank" rel="noreferrer">{"\u041e\u0442\u043a\u0440\u044b\u0442\u044c"}</a>
                  <button className="secondary-btn" type="button" onClick={() => void handleCopyInviteLink()}>
                    {"\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0441\u0441\u044b\u043b\u043a\u0443"}
                  </button>
                  <button className="secondary-btn" type="button" onClick={() => void handleCopyInviteMessage()}>
                    {"\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0442\u0435\u043a\u0441\u0442"}
                  </button>
                </div>
                <div className="users-invite-copy-state">
                  {inviteCopied ? <span className="success-text">{"\u0421\u0441\u044b\u043b\u043a\u0430 \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d\u0430"}</span> : null}
                  {inviteMessageCopied ? <span className="success-text">{"\u0422\u0435\u043a\u0441\u0442 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u0441\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u043d"}</span> : null}
                </div>
              </div>
            ) : null}
          </form>

          <div className="users-sidebar__filters">
            <div className="section-title">{"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438"}</div>
            <input className="desktop-input" placeholder={"\u041f\u043e\u0438\u0441\u043a \u043f\u043e \u0438\u043c\u0435\u043d\u0438 \u0438\u043b\u0438 email"} type="text" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} />
            <label className="checkbox-row users-checkbox-row">
              <input checked={onlyWithoutAccess} type="checkbox" onChange={(event) => setOnlyWithoutAccess(event.target.checked)} />
              <span className="checkbox-row__text">{"\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u0442\u043e\u043b\u044c\u043a\u043e \u0431\u0435\u0437 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443"}</span>
            </label>
            <div className="import-subtitle">{"\u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0442\u0435\u0445 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439, \u0443 \u043a\u043e\u0442\u043e\u0440\u044b\u0445 \u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u043c\u0443 \u043f\u0440\u043e\u0435\u043a\u0442\u0443."}</div>
          </div>

          <div className="project-list users-list">
            {visibleUsers.length === 0 ? <div className="project-chip">{"\u041d\u0438\u043a\u043e\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e"}</div> : null}
            {visibleUsers.map((user) => {
              const hasAccess = memberUserIds.has(user.id);
              return (
                <button key={user.id} type="button" className={user.id === selectedUserId ? "project-chip active" : "project-chip"} onClick={() => setSelectedUserId(user.id)}>
                  <strong>{user.full_name}</strong>
                  <span>{user.email}</span>
                  <div className="users-chip-row">
                    <span className={`users-role-badge users-role-badge--${user.role}`}>{getSystemRoleLabel(user.role)}</span>
                    <span className={hasAccess ? "users-access-badge is-connected" : "users-access-badge"}>{hasAccess ? "\u0415\u0441\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f" : "\u041d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430"}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="content-card users-content">
          <div className="users-header-row">
            <div>
              <div className="section-title">{"\u0420\u043e\u043b\u0438 \u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u044b"}</div>
              <div className="import-subtitle">{"\u0423\u043f\u0440\u0430\u0432\u043b\u044f\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u043e\u0439 \u0440\u043e\u043b\u044c\u044e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u043e\u043c \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0430\u043c \u0432 \u043e\u0434\u043d\u043e\u043c \u043c\u0435\u0441\u0442\u0435."}</div>
            </div>
            {currentUser ? <div className="project-chip">{`\u0410\u0434\u043c\u0438\u043d: ${currentUser.full_name}`}</div> : null}
          </div>

          {error ? <div className="error-banner">{error}</div> : null}
          {success ? <div className="success-text">{success}</div> : null}

          {selectedUser ? (
            <div className="users-admin-grid">
              <section className="sidebar-card users-card">
                <div className="section-title">{"\u0410\u043a\u043a\u0430\u0443\u043d\u0442"}</div>
                <div className="mini-input">{`Email: ${selectedUser.email}`}</div>
                <div className="desktop-filters-grid users-form-grid">
                  <label className="desktop-filter">
                    <span className="desktop-filter__label">{"\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u0430\u044f \u0440\u043e\u043b\u044c"}</span>
                    <select className="desktop-input" value={userRole} onChange={(event) => setUserRole(event.target.value)}>
                      {SYSTEM_ROLES.map((role) => (
                        <option key={role.key} value={role.key}>{role.label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="desktop-filter users-checkbox-field">
                    <span className="desktop-filter__label">{"\u0421\u0442\u0430\u0442\u0443\u0441"}</span>
                    <label className="checkbox-row">
                      <input checked={userActive} type="checkbox" onChange={(event) => setUserActive(event.target.checked)} />
                      <span className="checkbox-row__text">{"\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u0430\u043a\u0442\u0438\u0432\u0435\u043d"}</span>
                    </label>
                  </label>
                </div>
                <div className="actions-row">
                  <button className="primary-btn" type="button" onClick={() => void handleSaveUser()} disabled={savingUser}>
                    {savingUser ? "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u043c..." : "\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u0440\u043e\u043b\u044c"}
                  </button>
                  <button
                    className="secondary-btn"
                    type="button"
                    onClick={() => void handleDeleteUser()}
                    disabled={deletingUser || selectedUser.email.toLowerCase() === PRIMARY_OWNER_EMAIL || currentUser?.id === selectedUser.id}
                  >
                    {deletingUser ? "\u0423\u0434\u0430\u043b\u044f\u0435\u043c..." : "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f"}
                  </button>
                </div>
              </section>

              <section className="sidebar-card users-card">
                <div className="section-title">{"\u0414\u043e\u0441\u0442\u0443\u043f \u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443"}</div>
                <div className="desktop-filters-grid users-form-grid">
                  <label className="desktop-filter">
                    <span className="desktop-filter__label">{"\u041f\u0440\u043e\u0435\u043a\u0442"}</span>
                    <select className="desktop-input" value={selectedProjectId ?? ""} onChange={(event) => setSelectedProjectId(event.target.value ? Number(event.target.value) : null)}>
                      {projects.map((project) => (
                        <option key={project.id} value={project.id}>{project.name}</option>
                      ))}
                    </select>
                  </label>
                  <label className="desktop-filter">
                    <span className="desktop-filter__label">{"\u0420\u043e\u043b\u044c \u0432 \u043f\u0440\u043e\u0435\u043a\u0442\u0435"}</span>
                    <select className="desktop-input" value={memberRole} onChange={(event) => setMemberRole(event.target.value)}>
                      {PROJECT_ROLES.map((role) => (
                        <option key={role.key} value={role.key} disabled={role.key === "owner" && !canAssignOwner}>{role.label}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <form onSubmit={handleSaveAccess}>
                  <div className="actions-row">
                    <button className="primary-btn" type="submit" disabled={savingAccess || !selectedProject}>
                      {savingAccess ? "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u043c..." : selectedMembership ? "\u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f" : "\u0412\u044b\u0434\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f"}
                    </button>
                    {selectedMembership ? (
                      <button className="secondary-btn" type="button" onClick={() => void handleRemoveAccess()} disabled={savingAccess || selectedMembership.is_owner}>
                        {selectedMembership.is_owner ? "\u041d\u0435\u043b\u044c\u0437\u044f \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0432\u043b\u0430\u0434\u0435\u043b\u044c\u0446\u0430" : "\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f"}
                      </button>
                    ) : null}
                  </div>
                </form>
                <div className="mini-input">{selectedProject ? `${selectedProject.name} ? ${membersLoading ? "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430..." : `${members.length} \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a(\u043e\u0432)`}` : "\u041f\u0440\u043e\u0435\u043a\u0442 \u043d\u0435 \u0432\u044b\u0431\u0440\u0430\u043d"}</div>
              </section>
            </div>
          ) : (
            <div className="mini-input">{"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442."}</div>
          )}
        </section>
      </div>
    </main>
  );
}
