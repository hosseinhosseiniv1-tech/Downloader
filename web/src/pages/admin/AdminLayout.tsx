import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";

interface Props {
  apiKey: string | null;
  onLogout: () => void;
}

export default function AdminLayout({ apiKey, onLogout }: Props) {
  const { t } = useTranslation();
  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-bold">{t("admin")}</span>
            {apiKey && (
              <nav className="flex gap-1 text-sm">
                <NavItem to="/admin" end label={t("overview")} />
                <NavItem to="/admin/jobs" label={t("jobs")} />
                <NavItem to="/admin/users" label={t("users")} />
                <NavItem to="/admin/queue" label={t("queue")} />
                <NavItem to="/admin/config" label={t("config")} />
              </nav>
            )}
          </div>
          {apiKey && (
            <button className="btn-ghost" onClick={onLogout}>
              {t("logout")}
            </button>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function NavItem({ to, end, label }: { to: string; end?: boolean; label: string }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `rounded-lg px-3 py-1.5 ${isActive ? "bg-brand-600 text-white" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`
      }
    >
      {label}
    </NavLink>
  );
}