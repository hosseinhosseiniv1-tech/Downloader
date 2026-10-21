package logging

import (
	"os"
	"time"

	"github.com/rs/zerolog"
)

// New returns a JSON-configured zerolog logger using UTC timestamps.
func New(level string) zerolog.Logger {
	lvl, err := zerolog.ParseLevel(level)
	if err != nil {
		lvl = zerolog.InfoLevel
	}
	zerolog.TimeFieldFormat = time.RFC3339Nano
	zerolog.TimestampFunc = func() time.Time { return time.Now().UTC() }
	return zerolog.New(os.Stdout).Level(lvl).With().Timestamp().Logger()
}

// BootstrapError logs a fatal startup error to stderr with a fixed shape,
// so ops tooling can recognise it even before logging is configured.
func BootstrapError(stage string, err error) {
	l := zerolog.New(os.Stderr).With().Timestamp().Str("stage", stage).Logger()
	l.Error().Err(err).Msg("bootstrap_failed")
}