package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/queue"
)

// queueHandler serves GET /api/v1/queue.
func (d *Deps) queueHandler(c *gin.Context) {
	reader := queue.New(d.Redis)
	resp, err := reader.Snapshot(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "queue_unavailable"})
		return
	}
	c.JSON(http.StatusOK, resp)
}