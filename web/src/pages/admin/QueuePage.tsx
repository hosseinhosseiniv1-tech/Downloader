import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { adminQueue } from "../../lib/api";

export default function QueuePage({ apiKey }: { apiKey: string }) {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["queue"], queryFn: () => adminQueue(apiKey), refetchInterval: 3000 });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("queue")}</h1>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <div className="card">
          <p className="text-xs uppercase tracking-wide text-slate-500">{t("queue_depth")}</p>
          <p className="mt-1 text-3xl font-bold">{q.data?.depth ?? "—"}</p>
        </div>
        {q.data &&
          Object.entries(q.data.queues).map(([name, depth]) => (
            <div key={name} className="card">
              <p className="text-xs uppercase tracking-wide text-slate-500">{name}</p>
              <p className="mt-1 text-3xl font-bold">{depth}</p>
            </div>
          ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-950">
            <tr>
              <th className="px-4 py-3 text-start">{t("worker")}</th>
              <th className="px-4 py-3 text-start">Queues</th>
              <th className="px-4 py-3 text-start">Jobs</th>
              <th className="px-4 py-3 text-start">{t("state")}</th>
              <th className="px-4 py-3 text-start">{t("last_heartbeat")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {q.data?.workers.map((w) => (
              <tr key={w.name}>
                <td className="px-4 py-3 font-mono text-xs">{w.name}</td>
                <td className="px-4 py-3">{w.queues.join(", ")}</td>
                <td className="px-4 py-3">{w.job_count}</td>
                <td className="px-4 py-3">{w.state}</td>
                <td className="px-4 py-3 text-xs text-slate-500">{w.last_heartbeat}</td>
              </tr>
            ))}
            {q.data?.workers.length === 0 && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-slate-500">
                  {t("no_data")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}