import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function AdminLogin({ onLogin }: { onLogin: (key: string) => void }) {
  const { t } = useTranslation();
  const [key, setKey] = useState("");
  return (
    <div className="mx-auto max-w-md">
      <div className="card">
        <h2 className="text-xl font-bold">{t("admin_login")}</h2>
        <label className="mt-4 block text-sm font-medium" htmlFor="api-key">
          {t("admin_api_key")}
        </label>
        <input
          id="api-key"
          type="password"
          className="input mt-1"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && key.trim() && onLogin(key.trim())}
        />
        <button
          className="btn-primary mt-4 w-full"
          onClick={() => key.trim() && onLogin(key.trim())}
        >
          {t("admin_login_button")}
        </button>
      </div>
    </div>
  );
}