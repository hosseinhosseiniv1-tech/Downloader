package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/jobs"
)

// listUsersHandler serves GET /api/v1/users.
func (d *Deps) listUsersHandler(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	perPage, _ := strconv.Atoi(c.DefaultQuery("per_page", "25"))
	reader := jobs.New(d.Redis)
	resp, err := reader.ListUsers(c.Request.Context(), page, perPage)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "users_unavailable"})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// banUserHandler serves POST /api/v1/users/:id/ban.
func (d *Deps) banUserHandler(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid_id"})
		return
	}
	reader := jobs.New(d.Redis)
	if err := reader.Ban(c.Request.Context(), id); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "ban_failed"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true, "chat_id": id, "banned": true})
}