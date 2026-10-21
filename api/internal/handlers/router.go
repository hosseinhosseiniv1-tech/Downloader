package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/super-downloader/api/internal/logging"
)

// BuildRouter wires every HTTP route.
//
// Public routes (no auth):  /health, /identify, /download
// Admin routes (bearer):    everything under /api/v1/* except health
// Metrics:                  /metrics (Prometheus scrape endpoint)
func BuildRouter(d *Deps) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery())
	r.Use(logging.GinMiddleware(d.Log))
	r.Use(d.Metrics.GinMiddleware())

	// Prometheus scrape.
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Public health (no auth, also reachable via /api/v1/health for parity).
	r.GET("/health", d.healthHandler)
	r.GET("/api/v1/health", d.healthHandler)

	// Public API (rate limited by IP).
	public := r.Group("/api/v1")
	public.Use(d.ipRateLimitMiddleware())
	{
		public.POST("/identify", d.identifyHandler)
		public.POST("/download", d.downloadHandler)
	}

	// Admin API.
	admin := r.Group("/api/v1")
	admin.Use(d.AdminAuth.Middleware())
	{
		admin.GET("/stats", d.statsHandler)
		admin.GET("/jobs", d.listJobsHandler)
		admin.GET("/jobs/:id", d.getJobHandler)
		admin.GET("/users", d.listUsersHandler)
		admin.POST("/users/:id/ban", d.banUserHandler)
		admin.GET("/queue", d.queueHandler)
		admin.GET("/config", d.getConfigHandler)
		admin.POST("/config", d.updateConfigHandler)
	}

	// Friendly default 404.
	r.NoRoute(func(c *gin.Context) {
		c.JSON(http.StatusNotFound, gin.H{"error": "not_found"})
	})

	return r
}