"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homeRouteForRole } from "@/lib/auth";
import { RobotAvatar } from "@/components/RobotAvatar";
import { Spinner } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await login(identifier.trim(), password);
      router.replace(homeRouteForRole(user.role));
    } catch (err) {
      setError((err as Error).message || "We could not sign you in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center p-5">
      <div className="card grid w-full max-w-4xl overflow-hidden md:grid-cols-2">
        {/* Welcome / brand panel */}
        <div className="relative hidden flex-col justify-between bg-brand p-10 text-white md:flex">
          <div className="flex items-center gap-3 text-lg font-bold">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-white/15">🏡</span>
            NESTO Care
          </div>
          <div className="space-y-4">
            <RobotAvatar size={120} />
            <h1 className="text-3xl font-black leading-tight">
              Calm, connected
              <br />
              care — every day.
            </h1>
            <p className="max-w-xs text-white/80">
              One sign-in for patients, guardians, and care teams. Nesto takes you to the right place.
            </p>
          </div>
          <p className="text-sm text-white/60">Your assistant for a safe, simple day.</p>
        </div>

        {/* Sign-in form */}
        <form onSubmit={onSubmit} className="flex flex-col gap-5 p-8 md:p-10">
          <div className="md:hidden">
            <RobotAvatar size={64} />
          </div>
          <div>
            <h2 className="text-2xl font-black text-ink">Welcome back</h2>
            <p className="text-muted">Sign in to continue.</p>
          </div>

          <label className="flex flex-col gap-2 font-semibold text-ink-soft">
            Email or username
            <input
              type="text"
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="rounded-2xl border border-line bg-surface-soft px-4 py-3 text-lg text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/15"
              placeholder="you@example.com"
              required
            />
          </label>

          <label className="flex flex-col gap-2 font-semibold text-ink-soft">
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-2xl border border-line bg-surface-soft px-4 py-3 text-lg text-ink outline-none focus:border-brand focus:ring-4 focus:ring-brand/15"
              placeholder="••••••••"
              required
            />
          </label>

          {error ? (
            <p className="rounded-2xl border border-danger/20 bg-danger-soft px-4 py-3 font-semibold text-danger">{error}</p>
          ) : null}

          <button type="submit" className="btn-primary py-3.5 text-lg" disabled={busy}>
            {busy ? <Spinner className="border-white/40 border-t-white" /> : "Sign in"}
          </button>

          <p className="text-center text-sm text-muted">
            Patient · Guardian · Care team — all in one place.
          </p>
        </form>
      </div>
    </div>
  );
}
