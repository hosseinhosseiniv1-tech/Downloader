package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/auth"
	"github.com/super-downloader/api/internal/config"
	"github.com/super-downloader/api/internal/handlers"
	"github.com/super-downloader/api/internal/limiter"
	"github.com/super-downloader/api/internal/logging"
	"github.com/super-downloader/api/internal/metrics"
	"github.com/super-downloader/api/internal/redisclient"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		logging.BootstrapError("config", err)
		os.Exit(1)
	}

	log := logging.New(cfg.LogLevel)
	log.Info().Str("port", cfg.Port).Msg("api.starting")

	// Redis is a hard dependency. Fail fast.
	rc, err := redisclient.New(cfg.RedisURL)
	if err != nil {
		log.Error().Err(err).Msg("redis.init_failed")
		os.Exit(1)
	}
	pingCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	if err := rc.Ping(pingCtx); err != nil {
		cancel()
		log.Error().Err(err).Msg("redis.unreachable_at_startup")
		os.Exit(1)
	}
	cancel()
	log.Info().Msg("redis.connected")

	if cfg.Env == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	deps := &handlers.Deps{
		Log:          log,
		Redis:        rc,
		Cfg:          cfg,
		Metrics:      metrics.New(),
		Limiter:      limiter.New(rc, cfg.RateLimitPerMinute),
		AdminAuth:    auth.New(cfg.AdminAPIKey),
		HealthClient: &http.Client{Timeout: 2 * time.Second},
	}

	router := handlers.BuildRouter(deps)

	srv := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	go func() {
		log.Info().Str("addr", srv.Addr).Msg("api.listen")
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error().Err(err).Msg("api.listen_failed")
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	log.Info().Msg("api.shutting_down")
	ctx, cancelShutdown := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelShutdown()
	_ = srv.Shutdown(ctx)
	_ = rc.Close()
}