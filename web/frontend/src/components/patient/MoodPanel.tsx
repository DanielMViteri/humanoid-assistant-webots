"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type MoodReading } from "@/lib/api";
import { LiveBanner, Spinner } from "@/components/ui";

const MOODS = ["Happy", "Calm", "Sad", "Tired", "Worried", "Angry", "In pain", "Prefer not to say"];

export function MoodPanel({ robotName }: { robotName: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [since, setSince] = useState<number | null>(null);

  const tap = useMutation({
    mutationFn: (mood: string) => api<{ tapped_at_ms: number }>("/api/patient/mood", { method: "POST", body: { mood } }),
    onSuccess: (res) => setSince(res.tapped_at_ms),
  });

  const reading = useQuery({
    queryKey: ["mood-latest", since],
    queryFn: () => api<{ reading: MoodReading | null }>(`/api/patient/mood/latest?since_ms=${since}`),
    enabled: since != null,
    refetchInterval: 2500,
  });

  const r = reading.data?.reading;

  return (
    <div className="space-y-5">
      <p className="text-lg text-ink-soft">Tap the closest option. This is a simple wellbeing check-in.</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {MOODS.map((mood) => (
          <button
            key={mood}
            onClick={() => {
              setSelected(mood);
              tap.mutate(mood);
            }}
            className={`rounded-2xl border px-4 py-5 text-lg font-bold transition ${
              selected === mood
                ? "border-brand bg-brand-soft text-brand-strong"
                : "border-line bg-surface hover:bg-surface-soft text-ink"
            }`}
          >
            {mood}
          </button>
        ))}
      </div>

      {selected ? (
        <LiveBanner tone="success" icon="✅">
          Thank you. Your update was shared with your guardian.
        </LiveBanner>
      ) : null}

      {r?.mood ? (
        <LiveBanner tone="info" icon="🧠">
          {robotName} looked at you and sensed <strong>{title(r.mood)}</strong> ({Math.round(r.confidence * 100)}%
          confident, {r.capture_mode}).
        </LiveBanner>
      ) : since != null ? (
        <LiveBanner tone="muted" icon={<Spinner />}>
          {robotName} is reading your expression with its camera… this updates on its own.
        </LiveBanner>
      ) : null}
    </div>
  );
}

function title(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
