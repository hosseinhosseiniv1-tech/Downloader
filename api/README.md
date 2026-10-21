# Super Downloader — API

Go 1.22 + Gin, stateless, horizontally scalable.

## Endpoints

### Public

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness (Redis + local Bot API). |
| GET | `/api/v1/health` | Same, for parity with the rest of the API. |
| POST | `/api/v1/identify` | Extract metadata. |
| POST | `/api/v1/download` | Enqueue a job, return `job_id`. |

Both `/identify` and `/download` share the same Redis IP token bucket
(`RATE_LIMIT_PER_MINUTE`, default 60).

### Admin (`Authorization: Bearer $ADMIN_API_KEY`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/stats` | Aggregate counters + top platforms. |
| GET | `/api/v1/jobs` | Paginated jobs with filters. |
| GET | `/api/v1/jobs/:id` | Job detail, including `failed_upload_limit`. |
| GET | `/api/v1/users` | Paginated users with counts + banned flag. |
| POST | `/api/v1/users/:id/ban` | Set the `ban:{id}` Redis flag. |
| GET | `/api/v1/queue` | Live queue depth + per-worker load. |
| GET | `/api/v1/config` | Non-secret config + feature flags. |
| POST | `/api/v1/config` | Update feature flags. |

### Metrics

`GET /metrics` exposes Prometheus counters: `api_requests_total`,
`api_request_duration_seconds`, `jobs_queued_total`, `jobs_completed_total`,
`jobs_failed_total`, `upload_failures_total`, `download_bytes_total`.

## Environment

- `ADMIN_API_KEY` (required)
- `REDIS_PRIVATE_URL` or `REDIS_URL` (required)
- `LOCAL_BOT_API_URL` (default `http://local-bot-api.railway.internal:8081`)
- `METADATA_SERVICE_URL` (optional; default `http://worker.railway.internal:8091`)
- `RATE_LIMIT_PER_MINUTE` (default `60`)
- `PORT` / `API_PORT` (default `8080`)
- `ENV` (`development` | `production`)
- `LOG_LEVEL`

## Local development

```bash
cd api
go mod tidy
ADMIN_API_KEY=dev \
REDIS_PRIVATE_URL=redis://localhost:6379/0 \
go run ./cmd/api