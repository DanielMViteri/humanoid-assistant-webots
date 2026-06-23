"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homeRouteForRole } from "@/lib/auth";
import { RobotAvatar } from "@/components/RobotAvatar";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? homeRouteForRole(user.role) : "/login");
  }, [user, loading, router]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4">
      <RobotAvatar size={80} className="animate-pulse" />
      <p className="text-muted">Loading NESTO Care…</p>
    </div>
  );
}
