"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiLogin, apiRegister, storeSession } from "@/lib/api";

type AuthMode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const auth =
        mode === "register" ? await apiRegister(email, password, fullName) : await apiLogin(email, password);
      storeSession(auth);
      router.push("/projects");
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : mode === "register"
            ? "?? ??????? ??????????????????"
            : "?? ??????? ????????? ????";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-layout">
      <section className="login-card">
        <h1>
          {mode === "login" ? "???? ? ????????????? ???????" : "??????????? ? ????????????? ???????"}
        </h1>
        <p>??? ?? ??????? ?????????, ??? ? ? desktop-??????, ?? ??? ? ??????? ???-????????.</p>

        <div className="auth-switch-row">
          <button
            className={mode === "login" ? "primary-btn" : "ghost-btn"}
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
          >
            ????
          </button>
          <button
            className={mode === "register" ? "primary-btn" : "ghost-btn"}
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
          >
            ???????????
          </button>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          {mode === "register" ? (
            <input
              placeholder="??? ? ???????"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              required
            />
          ) : null}

          <input
            placeholder="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <input
            placeholder={mode === "register" ? "?????? (??????? 8 ????????)" : "??????"}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          {error ? <div className="error-banner">{error}</div> : null}

          <button className="primary-btn" disabled={isSubmitting} type="submit">
            {isSubmitting
              ? mode === "register"
                ? "????????????..."
                : "??????..."
              : mode === "register"
                ? "??????? ???????"
                : "?????"}
          </button>
        </form>
      </section>
    </main>
  );
}
