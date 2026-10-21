import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Route, Routes } from "react-router-dom";

import Landing from "./pages/Landing";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminLogin from "./pages/admin/AdminLogin";
import Overview from "./pages/admin/Overview";
import JobsPage from "./pages/admin/JobsPage";
import UsersPage from "./pages/admin/UsersPage";
import QueuePage from "./pages/admin/QueuePage";
import ConfigPage from "./pages/admin/ConfigPage";
import { useAdminKey } from "./hooks/useAdminKey";

export default function App() {
  const { i18n } = useTranslation();
  const { apiKey, login, logout } = useAdminKey();

  useEffect(() => {
    const isRtl = i18n.language === "fa";
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/admin" element={<AdminLayout apiKey={apiKey} onLogout={logout} />}>
        {apiKey ? (
          <>
            <Route index element={<Overview apiKey={apiKey} />} />
            <Route path="jobs" element={<JobsPage apiKey={apiKey} />} />
            <Route path="users" element={<UsersPage apiKey={apiKey} />} />
            <Route path="queue" element={<QueuePage apiKey={apiKey} />} />
            <Route path="config" element={<ConfigPage apiKey={apiKey} />} />
          </>
        ) : (
          <Route index element={<AdminLogin onLogin={login} />} />
        )}
      </Route>
    </Routes>
  );
}