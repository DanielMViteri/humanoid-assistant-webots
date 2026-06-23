"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LiveBanner, Spinner } from "@/components/ui";

export function SimpleActionPanel({
  description,
  buttonLabel,
  endpoint,
  successText,
  danger = false,
}: {
  description: string;
  buttonLabel: string;
  endpoint: string;
  successText: string;
  danger?: boolean;
}) {
  const action = useMutation({ mutationFn: () => api(endpoint, { method: "POST" }) });

  return (
    <div className="space-y-5">
      <p className="text-lg text-ink-soft">{description}</p>
      <button
        onClick={() => action.mutate()}
        disabled={action.isPending || action.isSuccess}
        className={`${danger ? "btn-danger" : "btn-primary"} px-8 py-4 text-lg`}
      >
        {action.isPending ? <Spinner className="border-white/40 border-t-white" /> : null} {buttonLabel}
      </button>
      {action.isSuccess ? (
        <LiveBanner tone={danger ? "danger" : "success"} icon={danger ? "🚨" : "✅"}>
          {successText}
        </LiveBanner>
      ) : null}
      {action.isError ? <LiveBanner tone="danger" icon="⚠️">Could not complete that. Please try again.</LiveBanner> : null}
    </div>
  );
}
