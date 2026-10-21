import { useTranslation } from "react-i18next";

import { Job } from "../../lib/api";

export function JobDetailDrawer({ job, onClose }: { job: Job; onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <aside className="absolute end-0 top-0 h-full w-full max-w-md overflow-y-auto bg-white shadow-xl dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800">
          <h2 className="font-bold">{t("detail")}</h2>
          <button className="btn-ghost" onClick={onClose}>
            {t("close")}
          </button>
        </div>
        <dl className="space-y-3 p-4 text-sm">
          <Row label="ID" value={<span className="font-mono">{job.id}</span>} />
          <Row label="Chat" value={job.chat_id} />
          <Row label={t("status")} value={job.status} />
          <Row label={t("platform")} value={job.platform || "—"} />
          <Row label={t("quality_col")} value={job.quality} />
          <Row label="URL" value={<span className="break-all text-xs">{job.url}</span>} />
          <Row label="Filesize" value={job.filesize ? `${(job.filesize / 1024 / 1024).toFixed(2)} MB` : "—"} />
          {job.error_code && <Row label="Error" value={`${job.error_code}: ${job.error_message ?? ""}`} />}
          <Row label={t("created")} value={new Date(job.created_at).toLocaleString()} />
          <Row label="Updated" value={new Date(job.updated_at).toLocaleString()} />
        </dl>
      </aside>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 break-words">{value}</dd>
    </div>
  );
}