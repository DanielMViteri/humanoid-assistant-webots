"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, type User } from "./api";

type AuthValue = {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<User>;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  async function login(identifier: string, password: string) {
    const res = await api<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: { identifier, password },
    });
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function homeRouteForRole(role: string): string {
  if (role === "elderly_user") return "/patient";
  if (role === "guardian_caregiver") return "/guardian";
  if (role === "admin_provider") return "/admin";
  return "/patient";
}
