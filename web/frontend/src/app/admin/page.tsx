"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminKpiDashboard } from "@/components/admin/AdminKpiDashboard";
import type { AdminKpiDashboardData } from "@/components/admin/admin_kpi_types";
import "@/components/admin/admin-kpi-dashboard.css";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function CenteredNotice({ text }: { text: string }) {
  return (
    <main className="operations-main">
      <div className="panel">{text}</div>
    </main>
  );
}

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [data, setData] = useState<AdminKpiDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState("snapshot");

  const isAdmin = user?.role === "admin_provider";

  // Once auth resolves, send non-admins somewhere they belong.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (!isAdmin) {
      router.replace("/");
    }
  }, [authLoading, user, isAdmin, router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<AdminKpiDashboardData>("/api/admin/kpis");
      setData(res);
    } catch (e) {
      setError((e as Error).message || "Failed to load admin KPIs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && isAdmin) {
      void load();
    }
  }, [authLoading, isAdmin, load]);

  if (authLoading) return <CenteredNotice text="Loading…" />;
  if (!user) return <CenteredNotice text="Redirecting to sign in…" />;
  if (!isAdmin) return <CenteredNotice text="This area is for care-team admins." />;

  // `data` is only dereferenced by the component when loading is false and there
  // is no error, by which point it has been set — so the cast is safe.
  return (
    <AdminKpiDashboard
      data={data as AdminKpiDashboardData}
      loading={loading}
      error={error}
      onRefresh={load}
      selectedRange={range}
      onRangeChange={setRange}
    />
  );
}
