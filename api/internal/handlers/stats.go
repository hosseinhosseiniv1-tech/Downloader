package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/stats"
)

// statsHandler serves GET /api/v1/stats.
func (d *Deps) statsHandler(c *gin.Context) {
	reader := stats.New(d.Redis)
	resp, err := reader.ComputeStats(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "stats_unavailable"})
		return
	}
	c.JSON(http.StatusOK, resp)
}