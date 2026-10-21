package stats

import (
	"context"
	"sort"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"

	"github.com/super-downloader/api/internal/models"
)

// Reader computes stats responses from Redis.
type Reader struct {
	rdb *redis.Client
}

// New constructs a Reader.
func New(rdb *redis.Client) *Reader {
	return &Reader{rdb: rdb}
}

// ComputeStats aggregates stats from the `stats:global` hash and, when
// available, per-platform counters.
func (r *Reader) ComputeStats(ctx context.Context) (*models.StatsResponse, error) {
	vals, err := r.rdb.HGetAll(ctx, "stats:global").Result()
	if err != nil && err != redis.Nil {
		return nil, err
	}

	resp := &models.StatsResponse{
		TopPlatforms: make([]models.PlatformCount, 0, 5),
	}

	get := func(field string) int64 {
		if v, ok := vals[field]; ok {
			return parseInt64(v)
		}
		return 0
	}

	resp.JobsQueued = get("jobs_queued")
	resp.JobsCompleted = get("jobs_completed")
	resp.JobsFailed = get("jobs_failed")
	resp.UploadFailures = get("upload_failures")
	resp.BytesDownloaded = get("bytes_downloaded")
	resp.TotalJobs = resp.JobsQueued + resp.JobsCompleted + resp.JobsFailed

	// Per-platform counters live in stats:platform:{name}.
	platformKeys, _ := r.rdb.Keys(ctx, "stats:platform:*").Result()
	for _, k := range platformKeys {
		v, _ := r.rdb.Get(ctx, k).Int64()
		if v > 0 {
			name := strings.TrimPrefix(k, "stats:platform:")
			resp.TopPlatforms = append(resp.TopPlatforms, models.PlatformCount{Platform: name, Count: v})
		}
	}
	sort.Slice(resp.TopPlatforms, func(i, j int) bool {
		return resp.TopPlatforms[i].Count > resp.TopPlatforms[j].Count
	})
	if len(resp.TopPlatforms) > 5 {
		resp.TopPlatforms = resp.TopPlatforms[:5]
	}

	// Active users in last 24 h: count rate:user:*:active keys created in
	// the last 24 h (approximation via SET key TTLs, but accurate enough
	// because we only care about users who had a job enqueued recently).
	cutoff := time.Now().Add(-24 * time.Hour).Unix()
	userKeys, _ := r.rdb.Keys(ctx, "stats:user:*:last_seen").Result()
	for _, k := range userKeys {
		v, _ := r.rdb.Get(ctx, k).Int64()
		if v >= cutoff {
			resp.ActiveUsers24h++
		}
	}

	return resp, nil
}

func parseInt64(s string) int64 {
	var n int64
	neg := false
	for _, c := range s {
		if c == '-' && n == 0 {
			neg = true
			continue
		}
		if c < '0' || c > '9' {
			break
		}
		n = n*10 + int64(c-'0')
	}
	if neg {
		return -n
	}
	return n
}