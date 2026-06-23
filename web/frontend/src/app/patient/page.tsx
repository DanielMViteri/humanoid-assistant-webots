"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type PatientHome, type RobotStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { RobotAvatar } from "@/components/RobotAvatar";
import { Spinner } from "@/components/ui";
import { MoodPanel } from "@/components/patient/MoodPanel";
import { TalkPanel } from "@/components/patient/TalkPanel";
import { FindPanel } from "@/components/patient/FindPanel";
import { SimpleActionPanel } from "@/components/patient/SimpleActionPanel";

type ActionKey =
  | "schedule"
  | "medication"
  | "talk"
  | "find_cane"
  | "find_medicine"
  | "call"
  | "mood"
  | "emergency";

export default function PatientPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [action, setAction] = useState<ActionKey | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  const homeQ = useQuery({
    queryKey: ["patient-home"],
    queryFn: () => api<PatientHome>("/api/patient/home"),
    enabled: !!user,
  });
  const robotQ = useQuery({
    queryKey: ["robot-status"],
    queryFn: () => api<RobotStatus>("/api/robot/status"),
    enabled: !!user,
    refetchInterval: 3500,
  });

  if (loading || !user || homeQ.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-3">
        <Spinner /> <span className="text-muted">Loading…</span>
      </div>
    );
  }
  if (homeQ.isError || !homeQ.data) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-danger">
        Could not reach the NESTO API. Make sure the backend is running on port 8000.
      </div>
    );
  }

  const home = homeQ.data;
  const robot = robotQ.data ?? home.robot;
  const p = home.patient;
  const robotName = p.robot_name || "Nesto";
  const objectLabel = p.important_object || "Cane";

  const actions: { key: ActionKey; icon: string; label: string; sub: string; danger?: boolean }[] = [
    { key: "schedule", icon: "📅", label: "Today's Schedule", sub: "See your day" },
    { key: "medication", icon: "💊", label: "Take Medication", sub: "Mark as taken" },
    { key: "talk", icon: "💬", label: `Talk to ${robotName}`, sub: "Press to speak" },
    { key: "find_cane", icon: "🔍", label: `Find My ${objectLabel}`, sub: `Locate your ${objectLabel.toLowerCase()}` },
    { key: "find_medicine", icon: "💊", label: "Find My Medicine", sub: "Locate medicine" },
    { key: "call", icon: "📞", label: `Call ${p.guardian.name}`, sub: "Make a call" },
    { key: "mood", icon: "🙂", label: "How are you feeling?", sub: "Mood check-in" },
    { key: "emergency", icon: "⚠️", label: "Emergency", sub: "Get help now", danger: true },
  ];

  const current = actions.find((a) => a.key === action) ?? null;

  return (
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-line bg-surface/85 backdrop-blur">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-4 px-5 py-3">
          <div className="flex items-center gap-2 text-lg font-black text-ink">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-soft">🏡</span> NESTO Care
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
            <StatChip label="Nesto" value={robot.status} dot />
            <StatChip label="Battery" value={`${robot.battery}%`} icon="🔋" />
            <StatChip label="Room" value={robot.room} icon="📍" />
          </div>
          <button onClick={logout} className="btn-secondary px-4 py-2 text-sm">
            Log out
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl space-y-6 px-5 py-6">
        {/* Greeting hero */}
        <section className="card flex items-center justify-between gap-4 p-6">
          <div>
            <h1 className="text-3xl font-black text-ink">Good day, {p.name} 💚</h1>
            <p className="mt-1 text-lg text-ink-soft">I&apos;m here to help you have a calm, safe, and connected day.</p>
          </div>
          <RobotAvatar size={96} className="hidden sm:block" />
        </section>

        {/* Action panel or grid */}
        {current ? (
          <section className="card space-y-5 p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-3 text-2xl font-black text-ink">
                <span>{current.icon}</span>
                {current.label}
              </h2>
              <button className="btn-secondary px-4 py-2 text-sm" onClick={() => setAction(null)}>
                Close
              </button>
            </div>
            <PanelBody action={action!} robotName={robotName} objectLabel={objectLabel} home={home} />
          </section>
        ) : (
          <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {actions.map((a) => (
              <button
                key={a.key}
                onClick={() => setAction(a.key)}
                className={`card flex flex-col items-start gap-2 p-5 text-left transition hover:-translate-y-0.5 hover:shadow-lg ${
                  a.danger ? "border-danger/20" : ""
                }`}
              >
                <span
                  className={`grid h-12 w-12 place-items-center rounded-2xl text-2xl ${
                    a.danger ? "bg-danger-soft" : "bg-brand-soft"
                  }`}
                >
                  {a.icon}
                </span>
                <span className={`text-lg font-black ${a.danger ? "text-danger" : "text-ink"}`}>{a.label}</span>
                <span className="text-sm text-muted">{a.sub}</span>
              </button>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}

function StatChip({ label, value, icon, dot }: { label: string; value: string; icon?: string; dot?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 font-semibold text-ink-soft">
      {dot ? <span className="h-2.5 w-2.5 rounded-full bg-brand" /> : <span>{icon}</span>}
      <span className="text-muted">{label}</span>
      <span className="text-ink">{value}</span>
    </span>
  );
}

function PanelBody({
  action,
  robotName,
  objectLabel,
  home,
}: {
  action: ActionKey;
  robotName: string;
  objectLabel: string;
  home: PatientHome;
}) {
  switch (action) {
    case "mood":
      return <MoodPanel robotName={robotName} />;
    case "talk":
      return <TalkPanel robotName={robotName} />;
    case "find_cane":
      return <FindPanel objectKey="cane" objectLabel={objectLabel} robotName={robotName} />;
    case "find_medicine":
      return <FindPanel objectKey="medicine" objectLabel="Medicine" robotName={robotName} />;
    case "medication":
      return (
        <SimpleActionPanel
          description={`Your ${home.patient.medicine_name} is scheduled for ${home.patient.medicine_time}. Mark it as taken when you have it.`}
          buttonLabel="✅ Mark as taken"
          endpoint="/api/patient/medication-taken"
          successText="Marked as taken. Your guardian was updated."
        />
      );
    case "call":
      return (
        <SimpleActionPanel
          description={`Ask ${robotName} to reach ${home.patient.guardian.name} (${home.patient.guardian.relationship}).`}
          buttonLabel={`📞 Call ${home.patient.guardian.name}`}
          endpoint="/api/patient/call"
          successText="Call request sent to your guardian."
        />
      );
    case "emergency":
      return (
        <SimpleActionPanel
          description="This alerts your guardian right away. It does not replace emergency services."
          buttonLabel="🚨 Alert my guardian"
          endpoint="/api/patient/emergency"
          successText="Urgent alert sent. Help is being notified."
          danger
        />
      );
    case "schedule":
      return <Schedule medicineTime={home.patient.medicine_time} />;
    default:
      return null;
  }
}

function Schedule({ medicineTime }: { medicineTime: string }) {
  const rows: [string, string][] = [
    ["08:00 AM", "Morning greeting & wellbeing check"],
    ["08:30 AM", "Breakfast"],
    [medicineTime, "Morning medicine"],
    ["10:00 AM", "Short walk"],
    ["12:00 PM", "Lunch"],
    ["06:00 PM", "Evening medicine"],
    ["08:30 PM", "Bedtime routine"],
  ];
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line">
      {rows.map(([time, task]) => (
        <li key={`${time}-${task}`} className="flex items-center justify-between bg-surface px-5 py-3">
          <span className="font-bold text-ink">{time}</span>
          <span className="text-ink-soft">{task}</span>
        </li>
      ))}
    </ul>
  );
}
