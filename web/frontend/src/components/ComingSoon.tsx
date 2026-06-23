"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { RobotAvatar } from "./RobotAvatar";

export function ComingSoon({ title, subtitle }: { title: string; subtitle: string }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <div className="card max-w-lg space-y-4 p-10 text-center">
        <RobotAvatar size={88} className="mx-auto" />
        <h1 className="text-2xl font-black text-ink">{title}</h1>
        <p className="text-lg text-ink-soft">{subtitle}</p>
        <button onClick={logout} className="btn-secondary mx-auto">
          Log out
        </button>
      </div>
    </div>
  );
}
