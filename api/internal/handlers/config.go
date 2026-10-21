package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/models"
)

// getConfigHandler serves GET /api/v1/config.
func (d *Deps) getConfigHandler(c *gin.Context) {
	flags, _ := d.Redis.HGetAll(c.Request.Context(), "config:flags").Result()
	flagsMap := map[string]bool{}
	for k, v := range flags {
		flagsMap[k] = v == "1" || v == "true"
	}
	resp := models.ConfigResponse{
		Version:         d.Cfg.Version,
		Environment:     d.Cfg.Env,
		FeatureFlags:    flagsMap,
		RateLimitPerMin: d.Cfg.RateLimitPerMinute,
		LocalBotAPIURL:  d.Cfg.LocalBotAPIURL,
	}
	c.JSON(http.StatusOK, resp)
}

// updateConfigHandler serves POST /api/v1/config — admin feature flags only.
func (d *Deps) updateConfigHandler(c *gin.Context) {
	var body map[string]bool
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid_body"})
		return
	}
	if len(body) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "empty_body"})
		return
	}
	mapping := map[string]string{}
	for k, v := range body {
		if v {
			mapping[k] = "1"
		} else {
			mapping[k] = "0"
		}
	}
	if err := d.Redis.HSet(c.Request.Context(), "config:flags", mapping).Err(); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "config_write_failed"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"ok": true, "updated": mapping})
}