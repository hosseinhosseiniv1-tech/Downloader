import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminBan, adminUsers } from "../../lib/api";

export default function UsersPage({ apiKey }: { apiKey: string }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-users", page], queryFn: () => adminUsers(apiKey, page) });

  const banMutation = useMutation({
    mutationFn: (id: number) => adminBan(apiKey, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{t("users")}</h1>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-950">
            <tr>
              <th className="px-4 py-3 text-start">Chat ID</th>
              <th className="px-4 py-3 text-start">{t("total_jobs")}</th>
              <th className="px-4 py-3 text-start">{t("created")}</th>
              <th className="px-4 py-3 text-start">{t("status")}</th>
              <th className="px-4 py-3 text-start">{t("actions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {q.data?.items.map((u) => (
              <tr key={u.chat_id}>
                <td className="px-4 py-3 font-mono text-xs">{u.chat_id}</td>
                <td className="px-4 py-3">{u.download_count}</td>
                <td className="px-4 py-3 text-xs text-slate-500">
                  {new Date(u.last_activity).toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  {u.banned ? (
                    <span className="badge bg-red-100 text-red-700">{t("banned")}</span>
                  ) : (
                    <span className="badge bg-emerald-100 text-emerald-700">ok</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button
                    className="btn-ghost text-xs"
                    onClick={() => banMutation.mutate(u.chat_id)}
                    disabled={u.banned || banMutation.isPending}
                  >
                    {u.banned ? t("unban") : t("ban")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {q.data && (
        <div className="flex items-center justify-between text-sm">
          <span>
            {t("page")} {q.data.page} {t("of")} {q.data.total_pages}
          </span>
          <div className="flex gap-2">
            <button className="btn-ghost" disabled={q.data.page <= 1} onClick={() => setPage((p) => p - 1)}>
              {t("prev")}
            </button>
            <button
              className="btn-ghost"
              disabled={q.data.page >= q.data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("next")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}