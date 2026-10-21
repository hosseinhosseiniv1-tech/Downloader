import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { adminQueue, adminStats } from "../../lib/api";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export default function Overview({ apiKey }: { apiKey: string }) {
  const { t } = useTranslation();
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => adminStats(apiKey) });
  const queue = useQuery({ queryKey: ["queue"], queryFn: () => adminQueue(apiKey), refetchInterval: 5000 });

  const s = stats.data;
  const successRate =
    s && s.jobs_completed + s.jobs_failed > 0
      ? ((s.jobs_completed / (s.jobs_completed + s.jobs_failed)) * 100).toFixed(1)
      : "—";

  const jobsByHour = buildJobsPerHourSeries();
  const bytesByDay = buildBytesPerDaySeries();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("overview")}</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard label={t("total_jobs")} value={fmt(s?.total_jobs)} />
        <StatCard label={t("success_rate")} value={`${successRate}%`} />
        <StatCard label={t("active_workers")} value={String(queue.data?.workers.length ?? "—")} />
        <StatCard label={t("queue_depth")} value={String(queue.data?.depth ?? "—")} />
        <StatCard
          label={t("upload_failures")}
          value={fmt(s?.upload_failures)}
          tone={s && s.upload_failures > 0 ? "danger" : "ok"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-4 font-semibold">{t("jobs_per_hour")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={jobsByHour}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="hour" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="mb-4 font-semibold">{t("bytes_per_day")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={bytesByDay}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => humanBytes(Number(v))} />
              <Tooltip formatter={(v) => humanBytes(Number(v))} />
              <Bar dataKey="bytes" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h3 className="mb-4 font-semibold">{t("top_platforms")}</h3>
        {s && s.top_platforms.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={s.top_platforms}
                dataKey="count"
                nameKey="platform"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {s.top_platforms.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-500">{t("no_data")}</p>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value?: string; tone?: "ok" | "danger" }) {
  return (
    <div className="card">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={`mt-1 text-2xl font-bold ${
          tone === "danger" ? "text-red-600" : tone === "ok" ? "text-emerald-600" : ""
        }`}
      >
        {value ?? "—"}
      </p>
    </div>
  );
}

function fmt(n?: number) {
  return n == null ? "—" : new Intl.NumberFormat().format(n);
}

function humanBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

// Placeholder series so the charts render even when the API doesn't expose
// per-hour / per-day histograms yet. In production these would come from a
// dedicated ``/api/v1/stats/timeseries`` endpoint.
function buildJobsPerHourSeries(): { hour: string; count: number }[] {
  const out: { hour: string; count: number }[] = [];
  for (let i = 23; i >= 0; i--) {
    const d = new Date(Date.now() - i * 3600_000);
    out.push({ hour: d.getUTCHours().toString().padStart(2, "0"), count: 0 });
  }
  return out;
}

function buildBytesPerDaySeries(): { day: string; bytes: number }[] {
  const out: { day: string; bytes: number }[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400_000);
    out.push({ day: `${d.getUTCMonth() + 1}/${d.getUTCDate()}`, bytes: 0 });
  }
  return out;
}