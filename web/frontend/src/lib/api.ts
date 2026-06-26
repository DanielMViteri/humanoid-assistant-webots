// Typed fetch wrapper for the NESTO Care API. Token is kept in localStorage.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const TOKEN_KEY = "nesto_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

type ApiOptions = { method?: string; body?: unknown };

export function withUiTriggeredAt<T extends Record<string, unknown>>(body?: T): T & { ui_triggered_at: number } {
  return { ...(body ?? ({} as T)), ui_triggered_at: Date.now() };
}

export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data?.detail ?? detail;
    } catch {
      /* ignore */
    }
    const err = new Error(detail) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return (await res.json()) as T;
}

// ---- Shared types ----
export type User = { id: string; name: string; role: string; patient_id: string };

export type PatientHome = {
  patient: {
    name: string;
    robot_name: string;
    important_object: string;
    medicine_name: string;
    medicine_time: string;
    guardian: { name: string; phone: string; relationship: string };
  };
  robot: RobotStatus;
};

export type RobotStatus = {
  online: boolean;
  status: string;
  battery: number;
  room: string;
  navigation: string;
  alerts: number;
  updated: string;
};

export type MoodReading = { mood: string; confidence: number; capture_mode: string; timestamp: number };
export type VoiceExchange = { transcript: string | null; reply: string | null };
