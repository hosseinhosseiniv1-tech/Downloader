package handlers

import "os"

// osGetenv is isolated so tests can swap it out.
func osGetenv(key string) string {
	return os.Getenv(key)
}