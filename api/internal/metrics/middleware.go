package metrics

import (
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// GinMiddleware records requests + durations into Prometheus.
func (m *Metrics) GinMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		c.Next()
		route := c.FullPath()
		if route == "" {
			route = "unmatched"
		}
		m.APIRequests.WithLabelValues(route, c.Request.Method, strconv.Itoa(c.Writer.Status())).Inc()
		m.APIDuration.WithLabelValues(route, c.Request.Method).Observe(time.Since(start).Seconds())
	}
}