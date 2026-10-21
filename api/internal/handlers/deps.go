package handlers

import (
	"net/http"

	"github.com/go-redis/redis/v8"
	"github.com/rs/zerolog"

	"github.com/super-downloader/api/internal/auth"
	"github.com/super-downloader/api/internal/config"
	"github.com/super-downloader/api/internal/limiter"
	"github.com/super-downloader/api/internal/metrics"
)

// Deps bundles every dependency a handler needs.
type Deps struct {
	Log          zerolog.Logger
	Redis        *redis.Client
	Cfg          *config.Config
	Metrics      *metrics.Metrics
	Limiter      *limiter.Limiter
	AdminAuth    *auth.Auth
	HealthClient *http.Client
}