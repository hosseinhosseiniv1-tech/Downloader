import { useCallback, useEffect, useState } from "react";

const KEY = "sd_admin_api_key";

export function useAdminKey() {
  const [apiKey, setApiKey] = useState<string | null>(() => localStorage.getItem(KEY));

  useEffect(() => {
    if (apiKey) localStorage.setItem(KEY, apiKey);
    else localStorage.removeItem(KEY);
  }, [apiKey]);

  const login = useCallback((key: string) => setApiKey(key), []);
  const logout = useCallback(() => setApiKey(null), []);

  return { apiKey, login, logout, isAuthed: Boolean(apiKey) };
}