package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds the entire API configuration, loaded from environment
// variables. Nothing is hard-coded.
type Config struct {
	Env                  string
	Port                 string
	LogLevel             string
	RedisURL             string
	AdminAPIKey          string
	LocalBotAPIURL       string
	POTServerURL         string
	RateLimitPerMinute   int
	Version              string
}

// Load reads environment variables and validates required ones.
func Load() (*Config, error) {
	adminKey := os.Getenv("ADMIN_API_KEY")
	if adminKey == "" {
		return nil, fmt.Errorf("ADMIN_API_KEY is required")
	}

	redisURL := os.Getenv("REDIS_PRIVATE_URL")
	if redisURL == "" {
		redisURL = os.Getenv("REDIS_URL")
	}
	if redisURL == "" {
		return nil, fmt.Errorf("REDIS_PRIVATE_URL or REDIS_URL is required")
	}

	rate := 60
	if v := os.Getenv("RATE_LIMIT_PER_MINUTE"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			rate = parsed
		}
	}

	env := os.Getenv("ENV")
	if env == "" {
		env = "development"
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = os.Getenv("API_PORT")
	}
	if port == "" {
		port = "8080"
	}

	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel == "" {
		logLevel = "INFO"
	}

	localBotAPI := os.Getenv("LOCAL_BOT_API_URL")
	if localBotAPI == "" {
		localBotAPI = "http://local-bot-api.railway.internal:8081"
	}

	return &Config{
		Env:                env,
		Port:               port,
		LogLevel:           logLevel,
		RedisURL:           redisURL,
		AdminAPIKey:        adminKey,
		LocalBotAPIURL:     localBotAPI,
		POTServerURL:       os.Getenv("POT_SERVER_URL"),
		RateLimitPerMinute: rate,
		Version:            os.Getenv("GIT_SHA"),
	}, nil
}