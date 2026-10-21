package auth

import (
	"crypto/subtle"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// Auth validates the static admin API key.
type Auth struct {
	key []byte
}

// New constructs an Auth with a raw key.
func New(key string) *Auth {
	return &Auth{key: []byte(key)}
}

// Middleware requires `Authorization: Bearer <key>` on the request.
func (a *Auth) Middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		header := c.GetHeader("Authorization")
		if header == "" || !strings.HasPrefix(header, "Bearer ") {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing_bearer_token"})
			return
		}
		token := strings.TrimPrefix(header, "Bearer ")
		if subtle.ConstantTimeCompare([]byte(token), a.key) != 1 {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid_api_key"})
			return
		}
		c.Next()
	}
}