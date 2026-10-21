package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// healthHandler returns ok/degraded based on Redis and the local Bot API.
func (d *Deps) healthHandler(c *gin.Context) {
	ctx := c.Request.Context()
	result := gin.H{"status": "ok"}

	// Redis.
	redisOK := true
	if err := d.Redis.Ping(ctx).Err(); err != nil {
		redisOK = false
	}
	result["redis"] = redisOK

	// Local Bot API.
	botOK := true
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, d.Cfg.LocalBotAPIURL+"/bot"+getBotToken()+"/getMe", nil)
	if err == nil {
		resp, reqErr := d.HealthClient.Do(req)
		if reqErr != nil {
			botOK = false
		} else {
			resp.Body.Close()
			if resp.StatusCode >= 500 {
				botOK = false
			}
		}
	} else {
		botOK = false
	}
	result["local_bot_api"] = botOK

	if !redisOK || !botOK {
		result["status"] = "degraded"
		c.JSON(http.StatusServiceUnavailable, result)
		return
	}
	result["timestamp"] = time.Now().UTC().Format(time.RFC3339)
	c.JSON(http.StatusOK, result)
}

// getBotToken is a small indirection so tests can override it.
var getBotToken = func() string {
	return envOr("TELEGRAM_BOT_TOKEN", "missing")
}

func envOr(key, fallback string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return fallback
}

// getenv is overridable in tests.
var getenv = func(key string) string {
	return osGetenv(key)
}