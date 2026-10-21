// Typed API client for Super Downloader.

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8080";

export type JobStatus =
  | "queued"
  | "downloading"
  | "uploading"
  | "completed"
  | "failed"
  | "failed_upload_limit";

export interface Job {
  id: string;
  chat_id: number;
  url: string;
  quality: string;
  status: JobStatus;
  platform: string;
  filesize: number;
  telegram_message_id?: string;
  error_code?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface JobList {
  items: Job[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface UserRow {
  chat_id: number;
  download_count: number;
  last_activity: string;
  banned: boolean;
}

export interface UserList {
  items: UserRow[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface StatsResponse {
  total_jobs: number;
  jobs_queued: number;
  jobs_completed: number;
  jobs_failed: number;
  upload_failures: number;
  bytes_downloaded: number;
  active_users_24h: number;
  top_platforms: { platform: string; count: number }[];
}

export interface QueueResponse {
  depth: number;
  workers: {
    name: string;
    queues: string[];
    job_count: number;
    state: string;
    last_heartbeat: string;
  }[];
  queues: Record<string, number>;
}

export interface ConfigResponse {
  version: string;
  environment: string;
  feature_flags: Record<string, boolean>;
  rate_limit_per_minute: number;
  local_bot_api_url: string;
}

export interface IdentifyResponse {
  title: string;
  uploader?: string;
  duration_seconds?: number;
  thumbnail?: string;
  available_qualities: string[];
  extractor?: string;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  apiKey?: string
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (apiKey) headers.set("Authorization", `Bearer ${apiKey}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) detail = body.error;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// --- Public ----------------------------------------------------------------

export async function identify(url: string): Promise<IdentifyResponse> {
  const raw = await request<Record<string, unknown>>("/api/v1/identify", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  // Accept both the flat shape and ``{ok, data}`` shape.
  const data = (raw as { ok?: boolean; data?: IdentifyResponse }).data ?? (raw as unknown as IdentifyResponse);
  return data;
}

export async function download(url: string, quality: string, chatId: number): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/api/v1/download", {
    method: "POST",
    body: JSON.stringify({ url, quality, chat_id: chatId }),
  });
}

export async function getJob(id: string, apiKey?: string): Promise<Job> {
  return request<Job>(`/api/v1/jobs/${id}`, {}, apiKey);
}

// --- Admin -----------------------------------------------------------------

export async function adminStats(key: string): Promise<StatsResponse> {
  return request<StatsResponse>("/api/v1/stats", {}, key);
}

export async function adminJobs(
  key: string,
  params: { page: number; per_page: number; status?: string; platform?: string }
): Promise<JobList> {
  const q = new URLSearchParams();
  q.set("page", String(params.page));
  q.set("per_page", String(params.per_page));
  if (params.status) q.set("status", params.status);
  if (params.platform) q.set("platform", params.platform);
  return request<JobList>(`/api/v1/jobs?${q.toString()}`, {}, key);
}

export async function adminUsers(key: string, page: number, per_page = 25): Promise<UserList> {
  return request<UserList>(`/api/v1/users?page=${page}&per_page=${per_page}`, {}, key);
}

export async function adminBan(key: string, id: number): Promise<void> {
  await request(`/api/v1/users/${id}/ban`, { method: "POST" }, key);
}

export async function adminQueue(key: string): Promise<QueueResponse> {
  return request<QueueResponse>("/api/v1/queue", {}, key);
}

export async function adminConfig(key: string): Promise<ConfigResponse> {
  return request<ConfigResponse>("/api/v1/config", {}, key);
}

export async function adminUpdateConfig(
  key: string,
  flags: Record<string, boolean>
): Promise<void> {
  await request(`/api/v1/config`, { method: "POST", body: JSON.stringify(flags) }, key);
}