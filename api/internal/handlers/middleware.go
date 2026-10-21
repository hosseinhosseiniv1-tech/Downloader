package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// ipRateLimitMiddleware uses the shared Redis token bucket keyed by client IP.
// Both /identify and /download share the same bucket.
func (d *Deps) ipRateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		ip := c.ClientIP()
		allowed, remaining, retryAfter := d.Limiter.Allow(c.Request.Context(), ip)
		c.Header("X-RateLimit-Limit", itoa(d.Cfg.RateLimitPerMinute))
		c.Header("X-RateLimit-Remaining", itoa(remaining))
		if !allowed {
			c.Header("Retry-After", itoa(retryAfter))
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error":               "rate_limited",
				"retry_after_seconds": retryAfter,
			})
			return
		}
		c.Next()
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	buf := make([]byte, 0, 12)
	for n > 0 {
		buf = append([]byte{byte('0' + n%10)}, buf...)
		n /= 10
	}
	if neg {
		buf = append([]byte{'-'}, buf...)
	}
	return string(buf)
}