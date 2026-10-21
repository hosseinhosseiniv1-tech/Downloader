import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export function Header() {
  const { t, i18n } = useTranslation();
  const toggleLang = () => {
    const next = i18n.language === "fa" ? "en" : "fa";
    i18n.changeLanguage(next);
    localStorage.setItem("sd_lang", next);
  };

  return (
    <header className="border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold">
          <span className="inline-block h-8 w-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700" />
          {t("brand")}
        </Link>
        <div className="flex items-center gap-3">
          <button className="btn-ghost" onClick={toggleLang}>
            {i18n.language === "fa" ? "🇬🇧 English" : "🇮🇷 فارسی"}
          </button>
          <Link to="/admin" className="btn-ghost">
            {t("admin")}
          </Link>
        </div>
      </div>
    </header>
  );
}