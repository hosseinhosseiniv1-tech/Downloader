package logging

import (
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/rs/zerolog"
)

const CorrelationKey = "correlation_id"

// GinMiddleware attaches a correlation ID (from X-Request-ID or generated)
// to the request context and logs one structured line per request.
func GinMiddleware(log zerolog.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		corr := c.GetHeader("X-Request-ID")
		if corr == "" {
			corr = uuid.NewString()
		}
		c.Set(CorrelationKey, corr)
		c.Writer.Header().Set("X-Request-ID", corr)

		c.Next()

		elapsed := time.Since(start)
		evt := log.Info()
		if c.Writer.Status() >= 500 {
			evt = log.Error()
		} else if c.Writer.Status() >= 400 {
			evt = log.Warn()
		}
		evt.
			Str("correlation_id", corr).
			Str("method", c.Request.Method).
			Str("path", c.Request.URL.Path).
			Int("status", c.Writer.Status()).
			Dur("duration_ms", elapsed).
			Str("ip", c.ClientIP()).
			Msg("http_request")
	}
}

// CorrelationID returns the correlation ID stored on the context.
func CorrelationID(c *gin.Context) string {
	if v, ok := c.Get(CorrelationKey); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}