"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { acceptInvite, fetchInviteInfo, storeSession, type InviteInfoResponse } from "@/lib/api";

function getRoleLabel(role: string): string {
  if (role === "admin") return "\u0410\u0434\u043c\u0438\u043d\u0438\u0441\u0442\u0440\u0430\u0442\u043e\u0440";
  if (role === "manager") return "\u041c\u0435\u043d\u0435\u0434\u0436\u0435\u0440";
  return "\u041a\u043b\u0438\u0435\u043d\u0442";
}

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const token = typeof params?.token === "string" ? params.token : "";
  const [info, setInfo] = useState<InviteInfoResponse | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadInvite() {
      if (!token) {
        setError("\u0421\u0441\u044b\u043b\u043a\u0430-\u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435 \u043d\u0435\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u044c\u043d\u0430.");
        setLoading(false);
        return;
      }

      try {
        const result = await fetchInviteInfo(token);
        setInfo(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435");
      } finally {
        setLoading(false);
      }
    }

    void loadInvite();
  }, [token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("\u041f\u0430\u0440\u043e\u043b\u0438 \u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434\u0430\u044e\u0442.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const auth = await acceptInvite(token, password);
      storeSession(auth);
      router.push("/projects");
    } catch (err) {
      setError(err instanceof Error ? err.message : "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u0438\u043d\u044f\u0442\u044c \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-card">
        <h1>{"\u041f\u0440\u0438\u043d\u044f\u0442\u044c \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435"}</h1>
        {loading ? <p>{"\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f..."}</p> : null}
        {!loading && info ? (
          <>
            <p>{"\u0417\u0430\u0432\u0435\u0440\u0448\u0438 \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430 \u0438 \u0437\u0430\u0434\u0430\u0439 \u043f\u0430\u0440\u043e\u043b\u044c \u0434\u043b\u044f \u0432\u0445\u043e\u0434\u0430 \u0432 \u0432\u0435\u0431-\u043a\u0430\u0431\u0438\u043d\u0435\u0442."}</p>
            <div className="mini-input">
              <strong>{info.full_name}</strong>
              <div>{info.email}</div>
              <div>{`\u0420\u043e\u043b\u044c: ${getRoleLabel(info.role)}`}</div>
            </div>
            <form className="form-grid" onSubmit={handleSubmit}>
              <input placeholder={"\u041f\u0430\u0440\u043e\u043b\u044c (\u043c\u0438\u043d\u0438\u043c\u0443\u043c 8 \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432)"} type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
              <input placeholder={"\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c"} type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
              {error ? <div className="error-banner">{error}</div> : null}
              <button className="primary-btn" disabled={submitting} type="submit">
                {submitting ? "\u0421\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u043c..." : "\u0410\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442"}
              </button>
            </form>
          </>
        ) : null}
        {!loading && !info && error ? <div className="error-banner">{error}</div> : null}
      </section>
    </main>
  );
}