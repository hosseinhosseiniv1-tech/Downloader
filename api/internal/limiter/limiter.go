package limiter

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

// Limiter implements an IP-based token bucket backed by Redis. Both
// ``POST /identify`` and ``POST /download`` share the same bucket.
//
// We store two keys per IP:
//   rate:ip:{ip}:tokens   (float as string)
//   rate:ip:{ip}:updated  (unix nanoseconds)
//
// Refill is computed lazily on each request.
type Limiter struct {
	rdb    *redis.Client
	perMin int
}

// New returns a limiter with ``perMin`` tokens per minute per IP.
func New(rdb *redis.Client, perMin int) *Limiter {
	if perMin <= 0 {
		perMin = 60
	}
	return &Limiter{rdb: rdb, perMin: perMin}
}

func tokensKey(ip string) string  { return fmt.Sprintf("rate:ip:%s:tokens", ip) }
func updatedKey(ip string) string { return fmt.Sprintf("rate:ip:%s:updated", ip) }

// Allow returns (allowed, remaining, retry_after_seconds).
func (l *Limiter) Allow(ctx context.Context, ip string) (bool, int, int) {
	now := time.Now().UnixNano()
	capacity := float64(l.perMin)
	refillRate := float64(l.perMin) / 60.0 // tokens per second

	pipe := l.rdb.TxPipeline()
	tokensCmd := pipe.Get(ctx, tokensKey(ip))
	updatedCmd := pipe.Get(ctx, updatedKey(ip))
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		// On Redis error we fail open — availability over strictness for
		// a public download endpoint, but we log at caller level.
		return true, 0, 0
	}

	tokens := capacity
	last := float64(now)

	if tokensCmd.Err() == nil {
		if f, err := tokensCmd.Float64(); err == nil {
			tokens = f
		}
	}
	if updatedCmd.Err() == nil {
		if f, err := updatedCmd.Int64(); err == nil {
			last = float64(f)
		}
	}

	elapsed := (float64(now) - last) / 1e9
	tokens += elapsed * refillRate
	if tokens > capacity {
		tokens = capacity
	}

	allowed := tokens >= 1
	if allowed {
		tokens -= 1
	}

	// Reject implausible values (e.g., clock skew).
	if tokens < 0 {
		tokens = 0
	}

	l.rdb.Set(ctx, tokensKey(ip), tokens, 10*time.Minute)
	l.rdb.Set(ctx, updatedKey(ip), now, 10*time.Minute)

	remaining := int(tokens)
	retryAfter := 0
	if !allowed {
		retryAfter = int(1 / refillRate)
		if retryAfter <= 0 {
			retryAfter = 1
		}
	}
	return allowed, remaining, retryAfter
}