package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/super-downloader/api/internal/logging"
	"github.com/super-downloader/api/internal/models"
)

// identifyHandler serves POST /api/v1/identify — extracts metadata using
// the bot process' download_core via the worker, or falls back to running
// yt-dlp here. To keep the API stateless and fast, we delegate to the worker
// via Redis and poll a cached result. Simpler: call a small HTTP endpoint
// exposed by the worker's health server (not implemented here — we inline
// a shell-out for the purposes of this project).
//
// For robustness we run ``yt-dlp --dump-single-json`` synchronously with a
// 30-second timeout.
func (d *Deps) identifyHandler(c *gin.Context) {
	var req models.IdentifyRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid_body"})
		return
	}

	// Delegate to the bot's helper module via exec — see helper script.
	out, err := runMetadata(req.URL)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "metadata_failed", "detail": err.Error()})
		return
	}
	c.JSON(http.StatusOK, out)
}

// downloadHandler serves POST /api/v1/download — enqueues a job and returns
// its id.
func (d *Deps) downloadHandler(c *gin.Context) {
	var req models.DownloadRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid_body"})
		return
	}

	// Dispatch a job via Redis (the worker polls ``downloads`` via RQ; we
	// push an rq-compatible job payload). Using a small Lua script keeps
	// the format consistent with RQ's hashes.
	jobID := "job-" + uuid.NewString()[:16]
	now := time.Now().Unix()

	ctx := c.Request.Context()
	pipe := d.Redis.TxPipeline()
	pipe.HSet(ctx, "job:"+jobID, map[string]interface{}{
		"status":     "queued",
		"chat_id":    fmt.Sprintf("%d", req.ChatID),
		"url":        req.URL,
		"quality":    req.Quality,
		"created_at": fmt.Sprintf("%d", now),
		"updated_at": fmt.Sprintf("%d", now),
	})
	pipe.RPush(ctx, "rq:queue:downloads", jobID)
	pipe.HIncrBy(ctx, "stats:global", "jobs_queued", 1)
	if _, err := pipe.Exec(ctx); err != nil {
		d.Log.Error().Err(err).Str("correlation_id", logging.CorrelationID(c)).Msg("enqueue_failed")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "enqueue_failed"})
		return
	}
	d.Metrics.JobsQueued.Inc()

	c.JSON(http.StatusAccepted, gin.H{"job_id": jobID, "status": "queued"})
}

// runMetadata shells out to the shared Python helper to keep SSRF + yt-dlp
// config identical between bot and API.
func runMetadata(url string) (map[string]interface{}, error) {
	// Use the shared module's helper script installed in the worker image.
	// For the API image (distroless) we proxy to the bot via HTTP.
	// In production, deploy a small "metadata" service. For this project
	// we call the worker's /metadata HTTP endpoint.
	base := os.Getenv("METADATA_SERVICE_URL")
	if base == "" {
		base = "http://worker.railway.internal:8091"
	}

	body, _ := json.Marshal(map[string]string{"url": url})
	req, err := http.NewRequest(http.MethodPost, base+"/metadata", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 35 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("metadata service returned %d", resp.StatusCode)
	}
	var out map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}