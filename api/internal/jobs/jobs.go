package jobs

import (
	"context"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"

	"github.com/super-downloader/api/internal/models"
)

// Reader lists jobs and users from Redis.
type Reader struct {
	rdb *redis.Client
}

// New constructs a Reader.
func New(rdb *redis.Client) *Reader {
	return &Reader{rdb: rdb}
}

// JobFilter controls the /jobs listing.
type JobFilter struct {
	Status   string
	Platform string
	From     time.Time
	To       time.Time
	Page     int
	PerPage  int
}

// ListJobs returns a paginated view of ``job:*`` hashes.
func (r *Reader) ListJobs(ctx context.Context, f JobFilter) (*models.JobList, error) {
	keys, err := r.rdb.Keys(ctx, "job:*").Result()
	if err != nil && err != redis.Nil {
		return nil, err
	}

	jobs := make([]models.Job, 0, len(keys))
	for _, k := range keys {
		raw, err := r.rdb.HGetAll(ctx, k).Result()
		if err != nil || len(raw) == 0 {
			continue
		}
		job := hashToJob(strings.TrimPrefix(k, "job:"), raw)
		if f.Status != "" && job.Status != f.Status {
			continue
		}
		if f.Platform != "" && job.Platform != f.Platform {
			continue
		}
		if !f.From.IsZero() && job.CreatedAt.Before(f.From) {
			continue
		}
		if !f.To.IsZero() && job.CreatedAt.After(f.To) {
			continue
		}
		jobs = append(jobs, job)
	}

	sort.Slice(jobs, func(i, j int) bool {
		return jobs[i].CreatedAt.After(jobs[j].CreatedAt)
	})

	total := int64(len(jobs))
	perPage := f.PerPage
	if perPage <= 0 {
		perPage = 25
	}
	page := f.Page
	if page <= 0 {
		page = 1
	}
	start := (page - 1) * perPage
	end := start + perPage
	if start > len(jobs) {
		start = len(jobs)
	}
	if end > len(jobs) {
		end = len(jobs)
	}
	totalPages := int((total + int64(perPage) - 1) / int64(perPage))
	if totalPages == 0 {
		totalPages = 1
	}

	return &models.JobList{
		Items:      jobs[start:end],
		Total:      total,
		Page:       page,
		PerPage:    perPage,
		TotalPages: totalPages,
	}, nil
}

// GetJob returns a single job by id, or nil if missing.
func (r *Reader) GetJob(ctx context.Context, id string) (*models.Job, error) {
	raw, err := r.rdb.HGetAll(ctx, "job:"+id).Result()
	if err != nil {
		return nil, err
	}
	if len(raw) == 0 {
		return nil, nil
	}
	job := hashToJob(id, raw)
	return &job, nil
}

// ListUsers returns a paginated view of users.
func (r *Reader) ListUsers(ctx context.Context, page, perPage int) (*models.UserList, error) {
	keys, err := r.rdb.Keys(ctx, "stats:user:*:downloads").Result()
	if err != nil && err != redis.Nil {
		return nil, err
	}

	users := make([]models.User, 0, len(keys))
	for _, k := range keys {
		// stats:user:{id}:downloads
		parts := strings.Split(k, ":")
		if len(parts) < 4 {
			continue
		}
		id, err := strconv.ParseInt(parts[2], 10, 64)
		if err != nil {
			continue
		}
		count, _ := r.rdb.Get(ctx, k).Int()
		lastSeenRaw, _ := r.rdb.Get(ctx, "stats:user:"+parts[2]+":last_seen").Int64()
		banned, _ := r.rdb.Exists(ctx, "ban:"+parts[2]).Result()
		users = append(users, models.User{
			ChatID:        id,
			DownloadCount: count,
			LastActivity:  time.Unix(lastSeenRaw, 0).UTC(),
			Banned:        banned > 0,
		})
	}

	sort.Slice(users, func(i, j int) bool {
		return users[i].LastActivity.After(users[j].LastActivity)
	})

	if perPage <= 0 {
		perPage = 25
	}
	if page <= 0 {
		page = 1
	}
	total := int64(len(users))
	start := (page - 1) * perPage
	end := start + perPage
	if start > len(users) {
		start = len(users)
	}
	if end > len(users) {
		end = len(users)
	}
	totalPages := int((total + int64(perPage) - 1) / int64(perPage))
	if totalPages == 0 {
		totalPages = 1
	}

	return &models.UserList{
		Items:      users[start:end],
		Total:      total,
		Page:       page,
		PerPage:    perPage,
		TotalPages: totalPages,
	}, nil
}

// Ban sets the ban flag for a user.
func (r *Reader) Ban(ctx context.Context, chatID int64) error {
	return r.rdb.Set(ctx, "ban:"+strconv.FormatInt(chatID, 10), "1", 0).Err()
}

func hashToJob(id string, raw map[string]string) models.Job {
	job := models.Job{ID: id}
	job.Status = raw["status"]
	job.ErrorCode = raw["error_code"]
	job.ErrorMessage = raw["error_message"]
	job.TelegramMsgID = raw["telegram_message_id"]
	if v, err := strconv.ParseInt(raw["chat_id"], 10, 64); err == nil {
		job.ChatID = v
	}
	if v, err := strconv.ParseInt(raw["filesize"], 10, 64); err == nil {
		job.Filesize = v
	}
	job.URL = raw["url"]
	job.Quality = raw["quality"]
	job.Platform = raw["platform"]
	if job.Platform == "" && job.URL != "" {
		job.Platform = detectPlatform(job.URL)
	}
	if ts, err := strconv.ParseInt(raw["updated_at"], 10, 64); err == nil {
		job.UpdatedAt = time.Unix(ts, 0).UTC()
	}
	if ts, err := strconv.ParseInt(raw["created_at"], 10, 64); err == nil {
		job.CreatedAt = time.Unix(ts, 0).UTC()
	} else {
		job.CreatedAt = job.UpdatedAt
	}
	return job
}

func detectPlatform(url string) string {
	switch {
	case strings.Contains(url, "youtube.com"), strings.Contains(url, "youtu.be"):
		return "youtube"
	case strings.Contains(url, "instagram.com"):
		return "instagram"
	case strings.Contains(url, "tiktok.com"):
		return "tiktok"
	case strings.Contains(url, "twitter.com"), strings.Contains(url, "x.com"):
		return "twitter"
	case strings.Contains(url, "facebook.com"):
		return "facebook"
	default:
		return "other"
	}
}