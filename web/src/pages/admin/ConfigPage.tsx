import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminConfig, adminUpdateConfig } from "../../lib/api";

export default function ConfigPage({ apiKey }: { apiKey: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["config"], queryFn: () => adminConfig(apiKey) });
  const [flags, setFlags] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (q.data) setFlags(q.data.feature_flags ?? {});
  }, [q.data]);

  const mutation = useMutation({
    mutationFn: () => adminUpdateConfig(apiKey, flags),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("config")}</h1>
      <div className="card space-y-3">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Row label="Version" value={q.data?.version || "—"} />
          <Row label="Environment" value={q.data?.environment || "—"} />
          <Row label="Rate limit / min" value={String(q.data?.rate_limit_per_minute ?? "—")} />
          <Row label="Local Bot API" value={q.data?.local_bot_api_url || "—"} />
        </div>
      </div>

      <div className="card">
        <h2 className="mb-3 font-semibold">{t("feature_flags")}</h2>
        <div className="space-y-2">
          {Object.entries(flags).length === 0 && (
            <p className="text-sm text-slate-500">{t("no_data")}</p>
          )}
          {Object.entries(flags).map(([name, enabled]) => (
            <label key={name} className="flex items-center gap-3 text-sm">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setFlags({ ...flags, [name]: e.target.checked })}
                className="h-4 w-4 rounded"
              />
              <span className="font-mono">{name}</span>
            </label>
          ))}
        </div>
        <button
          className="btn-primary mt-4"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isSuccess ? t("saved") : t("save")}
        </button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-xs">{value}</span>
    </>
  );
}