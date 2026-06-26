"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type VoiceExchange, withUiTriggeredAt } from "@/lib/api";
import { LiveBanner, Spinner } from "@/components/ui";

export function TalkPanel({ robotName }: { robotName: string }) {
  const [since, setSince] = useState<number | null>(null);

  const press = useMutation({
    mutationFn: () =>
      api<{ pressed_at_ms: number }>("/api/patient/voice/press-to-talk", { method: "POST", body: withUiTriggeredAt() }),
    onSuccess: (res) => setSince(res.pressed_at_ms),
  });

  const exchange = useQuery({
    queryKey: ["voice-latest", since],
    queryFn: () => api<{ exchange: VoiceExchange | null }>(`/api/patient/voice/latest?since_ms=${since}`),
    enabled: since != null,
    refetchInterval: 2500,
  });

  const ex = exchange.data?.exchange;

  return (
    <div className="space-y-5">
      <p className="text-lg text-ink-soft">
        Press to talk, then speak when {robotName} is listening. Your words appear here on their own.
      </p>

      <button onClick={() => press.mutate()} disabled={press.isPending} className="btn-primary px-8 py-4 text-lg">
        {press.isPending ? <Spinner className="border-white/40 border-t-white" /> : "🎤"} Press to talk
      </button>

      {ex?.transcript ? (
        <LiveBanner tone="success" icon="🎤">
          You said: <strong>{ex.transcript}</strong>
        </LiveBanner>
      ) : since != null ? (
        <LiveBanner tone="muted" icon={<Spinner />}>
          {robotName} is listening… speak now — your words will appear here.
        </LiveBanner>
      ) : null}

      {ex?.reply ? (
        <LiveBanner tone="info" icon="💬">
          {robotName}: {ex.reply}
        </LiveBanner>
      ) : null}
    </div>
  );
}
