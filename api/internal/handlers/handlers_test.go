package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/super-downloader/api/internal/auth"
	"github.com/super-downloader/api/internal/config"
	"github.com/super-downloader/api/internal/limiter"
	"github.com/super-downloader/api/internal/logging"
	"github.com/super-downloader/api/internal/metrics"
)

func setupTest(t *testing.T) (*gin.Engine, *miniredis.Miniredis) {
	t.Helper()
	mr := miniredis.RunT(t)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})

	cfg := &config.Config{
		Env:                "test",
		Port:               "0",
		LogLevel:           "ERROR",
		RedisURL:           "redis://" + mr.Addr(),
		AdminAPIKey:        "test-key",
		LocalBotAPIURL:     "http://127.0.0.1:0",
		RateLimitPerMinute: 10000,
	}

	d := &Deps{
		Log:          logging.New("ERROR"),
		Redis:        rdb,
		Cfg:          cfg,
		Metrics:      metrics.New(),
		Limiter:      limiter.New(rdb, 10000),
		AdminAuth:    auth.New("test-key"),
		HealthClient: &http.Client{Timeout: time.Second},
	}

	gin.SetMode(gin.TestMode)
	return BuildRouter(d), mr
}

func TestStatsAggregatesFromRedisHash(t *testing.T) {
	r, mr := setupTest(t)

	mr.HSet("stats:global", "jobs_queued", "10")
	mr.HSet("stats:global", "jobs_completed", "42")
	mr.HSet("stats:global", "jobs_failed", "3")
	mr.HSet("stats:global", "upload_failures", "1")
	mr.HSet("stats:global", "bytes_downloaded", "1048576")
	mr.Set("stats:platform:youtube", "50")
	mr.Set("stats:platform:tiktok", "20")

	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stats", nil)
	req.Header.Set("Authorization", "Bearer test-key")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	require.Equal(t, http.StatusOK, w.Code)
	var got map[string]interface{}
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &got))

	assert.EqualValues(t, 10, got["jobs_queued"])
	assert.EqualValues(t, 42, got["jobs_completed"])
	assert.EqualValues(t, 3, got["jobs_failed"])
	assert.EqualValues(t, 1, got["upload_failures"])
	assert.EqualValues(t, 1048576, got["bytes_downloaded"])
	assert.EqualValues(t, 55, got["total_jobs"])

	tops, ok := got["top_platforms"].([]interface{})
	require.True(t, ok)
	require.Len(t, tops, 2)
	first := tops[0].(map[string]interface{})
	assert.Equal(t, "youtube", first["platform"])
	assert.EqualValues(t, 50, first["count"])
}

func TestJobsListingFiltersAndPaginates(t *testing.T) {
	r, mr := setupTest(t)

	// Create 5 jobs across platforms and statuses.
	rows := []struct {
		id       string
		status   string
		platform string
		created  int64
	}{
		{"job-1", "completed", "youtube", 1000},
		{"job-2", "failed", "youtube", 2000},
		{"job-3", "completed", "tiktok", 3000},
		{"job-4", "failed_upload_limit", "youtube", 4000},
		{"job-5", "completed", "youtube", 5000},
	}
	for _, row := range rows {
		mr.HSet("job:"+row.id, "status", row.status)
		mr.HSet("job:"+row.id, "platform", row.platform)
		mr.HSet("job:"+row.id, "created_at", itoa64(row.created))
		mr.HSet("job:"+row.id, "updated_at", itoa64(row.created))
	}

	// Filter by status=completed, page 1, per_page=2.
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/jobs?status=completed&per_page=2&page=1", nil)
	req.Header.Set("Authorization", "Bearer test-key")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	require.Equal(t, http.StatusOK, w.Code)

	var got map[string]interface{}
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &got))

	assert.EqualValues(t, 3, got["total"])
	assert.EqualValues(t, 2, got["per_page"])
	assert.EqualValues(t, 1, got["page"])
	assert.EqualValues(t, 2, got["total_pages"])

	items, ok := got["items"].([]interface{})
	require.True(t, ok)
	require.Len(t, items, 2)
	// Sorted newest first → job-5 then job-3.
	first := items[0].(map[string]interface{})
	assert.Equal(t, "job-5", first["id"])
}

func TestJobsFilterByPlatform(t *testing.T) {
	r, mr := setupTest(t)
	mr.HSet("job:a", "status", "completed")
	mr.HSet("job:a", "platform", "youtube")
	mr.HSet("job:a", "created_at", "100")
	mr.HSet("job:a", "updated_at", "100")
	mr.HSet("job:b", "status", "completed")
	mr.HSet("job:b", "platform", "tiktok")
	mr.HSet("job:b", "created_at", "200")
	mr.HSet("job:b", "updated_at", "200")

	req, _ := http.NewRequest(http.MethodGet, "/api/v1/jobs?platform=tiktok", nil)
	req.Header.Set("Authorization", "Bearer test-key")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	var got map[string]interface{}
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &got))
	assert.EqualValues(t, 1, got["total"])
}

func TestAdminRequiresBearer(t *testing.T) {
	r, _ := setupTest(t)
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stats", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	assert.Equal(t, http.StatusUnauthorized, w.Code)
}

func TestBanUserWritesRedisFlag(t *testing.T) {
	r, mr := setupTest(t)

	req, _ := http.NewRequest(http.MethodPost, "/api/v1/users/42/ban", nil)
	req.Header.Set("Authorization", "Bearer test-key")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	assert.Equal(t, http.StatusOK, w.Code)
	assert.True(t, mr.Exists("ban:42"))
}

func TestHealthDegradedWhenBotMissing(t *testing.T) {
	r, _ := setupTest(t)
	// LocalBotAPIURL points to 127.0.0.1:0, so the request fails.
	getBotToken = func() string { return "x" }
	defer func() { getBotToken = func() string { return os.Getenv("TELEGRAM_BOT_TOKEN") } }()

	req, _ := http.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	assert.Equal(t, http.StatusServiceUnavailable, w.Code)
	var body map[string]interface{}
	require.NoError(t, json.Unmarshal(w.Body.Bytes(), &body))
	assert.Equal(t, "degraded", body["status"])
}

func itoa64(n int64) string {
	if n == 0 {
		return "0"
	}
	buf := []byte{}
	for n > 0 {
		buf = append([]byte{byte('0' + n%10)}, buf...)
		n /= 10
	}
	return string(buf)
}

var _ = context.Background // keep import used if future tests need it