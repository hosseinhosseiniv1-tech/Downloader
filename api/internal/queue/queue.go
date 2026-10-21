package queue

import (
	"context"
	"strings"

	"github.com/go-redis/redis/v8"

	"github.com/super-downloader/api/internal/models"
)

// Reader reads RQ queue state from Redis.
type Reader struct {
	rdb *redis.Client
}

// New returns a Reader.
func New(rdb *redis.Client) *Reader {
	return &Reader{rdb: rdb}
}

// Snapshot returns live queue depth plus per-worker load.
func (r *Reader) Snapshot(ctx context.Context) (*models.QueueResponse, error) {
	queues := map[string]int64{}
	for _, name := range []string{"downloads", "maintenance"} {
		n, _ := r.rdb.LLen(ctx, "rq:queue:"+name).Result()
		queues[name] = n
	}
	depth := int64(0)
	for _, n := range queues {
		depth += n
	}

	workers := []models.WorkerLoad{}
	keys, _ := r.rdb.Keys(ctx, "rq:worker:*").Result()
	for _, k := range keys {
		raw, _ := r.rdb.HGetAll(ctx, k).Result()
		if len(raw) == 0 {
			continue
		}
		name := strings.TrimPrefix(k, "rq:worker:")
		queueList := strings.Split(raw["queues"], ",")
		workers = append(workers, models.WorkerLoad{
			Name:     name,
			Queues:   queueList,
			JobCount: parseInt(raw["job_count"]),
			State:    raw["state"],
			LastSeen: raw["last_heartbeat"],
		})
	}

	return &models.QueueResponse{
		Depth:   int(depth),
		Workers: workers,
		Queues:  queues,
	}, nil
}

func parseInt(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			break
		}
		n = n*10 + int(c-'0')
	}
	return n
}