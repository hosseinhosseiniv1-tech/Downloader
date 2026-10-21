import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { Job, adminJobs } from "../../lib/api";
import { JobDetailDrawer } from "./JobDetailDrawer";

const STATUSES = ["", "queued", "downloading", "uploading", "completed", "failed", "failed_upload_limit"];
const PLATFORMS = ["", "youtube", "instagram", "tiktok", "twitter", "facebook", "other"];

export default function JobsPage({ apiKey }: { apiKey: string }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [platform, setPlatform] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);

  const q = useQuery({
    queryKey: ["admin-jobs", page, status, platform],
    queryFn: () => adminJobs(apiKey, { page, per_page: 25, status, platform }),
  });

  const data = q.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("jobs")}</h1>
        <div className="flex flex-wrap gap-2">
          <select
            className="input w-auto py-2"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === "" ? t("all") : s}
              </option>
            ))}
          </select>
          <select
            className="input w-auto py-2"
            value={platform}
            onChange={(e) => {
              setPlatform(e.target.value);
              setPage(1);
            }}
          >
            {PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p === "" ? t("all") : p}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-950">
            <tr>
              <Th>ID</Th>
              <Th>{t("status")}</Th>
              <Th>{t("platform")}</Th>
              <Th>{t("quality_col")}</Th>
              <Th>{t("created")}</Th>
              <Th>{t("actions")}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {q.isLoading && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-slate-500">
                  {t("loading")}
                </td>
              </tr>
            )}
            {data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-slate-500">
                  {t("no_data")}
                </td>
              </tr>
            )}
            {data?.items.map((j) => (
              <tr key={j.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="px-4 py-3 font-mono text-xs">{j.id}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={j.status} />
                </td>
                <td className="px-4 py-3">{j.platform}</td>
                <td className="px-4 py-3">{j.quality}</td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {new Date(j.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <button className="btn-ghost text-xs" onClick={() => setSelected(j)}>
                    {t("view")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && (
        <div className="flex items-center justify-between text-sm">
          <span>
            {t("page")} {data.page} {t("of")} {data.total_pages} · {data.total}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-ghost"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={data.page <= 1}
            >
              {t("prev")}
            </button>
            <button
              className="btn-ghost"
              onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
              disabled={data.page >= data.total_pages}
            >
              {t("next")}
            </button>
          </div>
        </div>
      )}

      {selected && <JobDetailDrawer job={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-4 py-3 text-start text-xs font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </th>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    failed: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    failed_upload_limit: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    queued: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    downloading: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    uploading: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  };
  return <span className={`badge ${styles[status] ?? styles.queued}`}>{status}</span>;
}