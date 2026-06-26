"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, withUiTriggeredAt } from "@/lib/api";
import { LiveBanner, Spinner } from "@/components/ui";

export function FindPanel({
  objectKey,
  objectLabel,
  robotName,
}: {
  objectKey: "cane" | "medicine";
  objectLabel: string;
  robotName: string;
}) {
  const [started, setStarted] = useState(false);

  const memory = useQuery({
    queryKey: ["object-memory", objectKey],
    queryFn: () => api<{ object: string; location: string | null }>(`/api/patient/object-memory/${objectKey}`),
  });

  const start = useMutation({
    mutationFn: () => api("/api/patient/find-object", { method: "POST", body: withUiTriggeredAt({ object: objectKey }) }),
    onSuccess: () => setStarted(true),
  });

  const location = memory.data?.location;
  const lower = objectLabel.toLowerCase();

  return (
    <div className="space-y-5">
      {location ? (
        <LiveBanner tone="info" icon="🧠">
          {robotName} remembers your {lower} was last in the <strong>{title(location)}</strong>.
        </LiveBanner>
      ) : (
        <p className="text-lg text-ink-soft">
          {robotName} will check the last known location and search nearby rooms for your {lower}.
        </p>
      )}

      <ol className="space-y-2 rounded-2xl bg-surface-soft p-5 text-ink-soft">
        <li>1. Checking last known location…</li>
        <li>2. Searching nearby rooms…</li>
        <li>3. Looking for the {lower} using object memory…</li>
      </ol>

      <button onClick={() => start.mutate()} disabled={start.isPending || started} className="btn-primary px-8 py-4 text-lg">
        {start.isPending ? <Spinner className="border-white/40 border-t-white" /> : "🔍"}{" "}
        {started ? "Search started" : "Start search"}
      </button>

      {started ? (
        <LiveBanner tone="success" icon="✅">
          Search started. Please wait nearby while {robotName} checks the home.
        </LiveBanner>
      ) : null}
    </div>
  );
}

function title(s: string) {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}
