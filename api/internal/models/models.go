package models

import "time"

// JobStatus is the canonical status of a download job.
type JobStatus string

const (
	StatusQueued            JobStatus = "queued"
	StatusDownloading       JobStatus = "downloading"
	StatusUploading         JobStatus = "uploading"
	StatusCompleted         JobStatus = "completed"
	StatusFailed            JobStatus = "failed"
	StatusFailedUploadLimit JobStatus = "failed_upload_limit"
)

// Job is the serialised view of a job as exposed by the API.
type Job struct {
	ID            string    `json:"id"`
	ChatID        int64     `json:"chat_id"`
	URL           string    `json:"url"`
	Quality       string    `json:"quality"`
	Status        string    `json:"status"`
	Platform      string    `json:"platform"`
	Filesize      int64     `json:"filesize"`
	TelegramMsgID string    `json:"telegram_message_id,omitempty"`
	ErrorCode     string    `json:"error_code,omitempty"`
	ErrorMessage  string    `json:"error_message,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// JobList is the paginated response.
type JobList struct {
	Items      []Job `json:"items"`
	Total      int64 `json:"total"`
	Page       int   `json:"page"`
	PerPage    int   `json:"per_page"`
	TotalPages int   `json:"total_pages"`
}

// User is the serialised user record.
type User struct {
	ChatID       int64     `json:"chat_id"`
	DownloadCount int      `json:"download_count"`
	LastActivity time.Time `json:"last_activity"`
	Banned       bool      `json:"banned"`
}

// UserList is a paginated user response.
type UserList struct {
	Items      []User `json:"items"`
	Total      int64  `json:"total"`
	Page       int    `json:"page"`
	PerPage    int    `json:"per_page"`
	TotalPages int    `json:"total_pages"`
}

// StatsResponse is returned by GET /api/v1/stats.
type StatsResponse struct {
	TotalJobs       int64            `json:"total_jobs"`
	JobsQueued      int64            `json:"jobs_queued"`
	JobsCompleted   int64            `json:"jobs_completed"`
	JobsFailed      int64            `json:"jobs_failed"`
	UploadFailures  int64            `json:"upload_failures"`
	BytesDownloaded int64            `json:"bytes_downloaded"`
	ActiveUsers24h  int64            `json:"active_users_24h"`
	TopPlatforms    []PlatformCount  `json:"top_platforms"`
}

// PlatformCount represents a (platform, count) tuple in the stats response.
type PlatformCount struct {
	Platform string `json:"platform"`
	Count    int64  `json:"count"`
}

// QueueResponse is returned by GET /api/v1/queue.
type QueueResponse struct {
	Depth       int              `json:"depth"`
	Workers     []WorkerLoad     `json:"workers"`
	Queues      map[string]int64 `json:"queues"`
}

// WorkerLoad describes a single RQ worker.
type WorkerLoad struct {
	Name      string   `json:"name"`
	Queues    []string `json:"queues"`
	JobCount  int      `json:"job_count"`
	State     string   `json:"state"`
	LastSeen  string   `json:"last_heartbeat"`
}

// ConfigResponse is returned by GET /api/v1/config.
type ConfigResponse struct {
	Version           string            `json:"version"`
	Environment       string            `json:"environment"`
	FeatureFlags      map[string]bool   `json:"feature_flags"`
	RateLimitPerMin   int               `json:"rate_limit_per_minute"`
	LocalBotAPIURL    string            `json:"local_bot_api_url"`
}

// IdentifyRequest is the body of POST /identify.
type IdentifyRequest struct {
	URL string `json:"url" binding:"required"`
}

// DownloadRequest is the body of POST /download.
type DownloadRequest struct {
	URL     string `json:"url"     binding:"required"`
	Quality string `json:"quality" binding:"required"`
	ChatID  int64  `json:"chat_id" binding:"required"`
}