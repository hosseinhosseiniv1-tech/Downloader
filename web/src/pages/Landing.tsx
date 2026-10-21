import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Header } from "../components/Header";
import {
  ApiError,
  Job,
  download,
  getJob,
  identify,
  IdentifyResponse,
} from "../lib/api";

const QUALITIES = ["best", "1080p", "720p", "480p", "audio"] as const;
type Quality = (typeof QUALITIES)[number];

export default function Landing() {
  const { t } = useTranslation();
  const [url, setUrl] = useState("");
  const [meta, setMeta] = useState<IdentifyResponse | null>(null);
  const [quality, setQuality] = useState<Quality>("best");
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const identifyMutation = useMutation({
    mutationFn: identify,
    onSuccess: (data) => {
      setMeta(data);
      setError(null);
      // Default to the highest available non-"best" quality, if any.
      const pick = QUALITIES.find((q) => q !== "audio" && data.available_qualities.includes(q)) ?? "best";
      setQuality(pick as Quality);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Identify failed");
      setMeta(null);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: () => download(url, quality, Number(import.meta.env.VITE_CHAT_ID ?? 0)),
    onSuccess: (data) => {
      setJobId(data.job_id);
      setError(null);
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Download failed");
    },
  });

  const jobQuery = useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s) return 2000;
      return ["completed", "failed", "failed_upload_limit"].includes(s) ? false : 2000;
    },
  });

  const isPolling =
    jobQuery.data && ["queued", "downloading", "uploading"].includes(jobQuery.data.status);

  return (
    <div className="min-h-full">
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="text-center text-4xl font-extrabold tracking-tight sm:text-5xl">
          {t("brand")}
        </h1>
        <p className="mt-3 text-center text-lg text-slate-600 dark:text-slate-300">{t("tagline")}</p>

        <div className="card mt-8">
          <label className="mb-2 block text-sm font-medium" htmlFor="url">
            {t("url_label")}
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="url"
              className="input flex-1"
              placeholder={t("url_placeholder")}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={identifyMutation.isPending || isPolling}
            />
            <button
              className="btn-primary sm:w-auto"
              onClick={() => identifyMutation.mutate(url.trim())}
              disabled={!url.trim() || identifyMutation.isPending}
            >
              {identifyMutation.isPending ? t("identifying") : t("identify")}
            </button>
          </div>

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

          {meta && (
            <div className="mt-6 border-t border-slate-200 pt-6 dark:border-slate-800">
              <div className="flex items-start gap-4">
                {meta.thumbnail && (
                  <img
                    src={meta.thumbnail}
                    alt=""
                    className="h-24 w-40 flex-shrink-0 rounded-lg object-cover ring-1 ring-slate-200 dark:ring-slate-800"
                  />
                )}
                <div className="min-w-0">
                  <p className="line-clamp-2 font-semibold">{meta.title}</p>
                  <p className="text-sm text-slate-500">
                    {meta.uploader ?? "—"} · {meta.extractor ?? "—"}
                  </p>
                </div>
              </div>

              <fieldset className="mt-5">
                <legend className="mb-2 block text-sm font-medium">{t("quality")}</legend>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {QUALITIES.map((q) => {
                    const available = meta.available_qualities.includes(q);
                    const selected = quality === q;
                    return (
                      <button
                        key={q}
                        type="button"
                        onClick={() => setQuality(q)}
                        disabled={!available}
                        className={[
                          "rounded-xl border px-3 py-2.5 text-sm font-medium transition-all",
                          selected
                            ? "border-brand-600 bg-brand-50 text-brand-700 dark:bg-brand-900/40"
                            : "border-slate-200 hover:border-slate-300 dark:border-slate-700",
                          !available && "cursor-not-allowed opacity-40",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        {labelForQuality(q)}
                      </button>
                    );
                  })}
                </div>
              </fieldset>

              <button
                className="btn-primary mt-5 w-full sm:w-auto"
                onClick={() => downloadMutation.mutate()}
                disabled={downloadMutation.isPending || isPolling}
              >
                {downloadMutation.isPending ? "…" : t("download")}
              </button>
            </div>
          )}

          {jobQuery.data && (
            <div className="mt-6 rounded-xl bg-slate-50 p-4 dark:bg-slate-900/60">
              <p className="text-sm font-medium">
                {jobQuery.data.status === "completed" && t("job_completed")}
                {jobQuery.data.status === "failed_upload_limit" && (
                  <span className="text-red-600">{t("failed_upload_limit")}</span>
                )}
                {jobQuery.data.status === "failed" && (
                  <span className="text-red-600">
                    {t("job_failed")}: {jobQuery.data.error_message ?? "unknown"}
                  </span>
                )}
                {isPolling && t("polling")}
              </p>
              {jobQuery.data.status === "completed" && (
                <a
                  className="btn-primary mt-3"
                  href={`https://t.me/${import.meta.env.VITE_BOT_USERNAME ?? "StoaderBot"}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("send_to_telegram")}
                </a>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function labelForQuality(q: Quality): string {
  switch (q) {
    case "best":
      return "✨ Best";
    case "1080p":
      return "🎥 1080p";
    case "720p":
      return "🎥 720p";
    case "480p":
      return "🎥 480p";
    case "audio":
      return "🎵 MP3";
  }
}