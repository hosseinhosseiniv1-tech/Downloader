package redisclient

import (
	"context"
	"time"

	"github.com/go-redis/redis/v8"
)

// Client is a thin wrapper around go-redis that centralises retry/timeout
// policy.
type Client struct {
	*redis.Client
}

// New builds a Redis client from a URL. Returns an error if the URL is
// malformed.
func New(url string) (*Client, error) {
	opt, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}
	opt.DialTimeout = 3 * time.Second
	opt.ReadTimeout = 5 * time.Second
	opt.WriteTimeout = 5 * time.Second
	opt.PoolSize = 20
	opt.MinIdleConns = 2
	return &Client{Client: redis.NewClient(opt)}, nil
}

// Ping with a caller-supplied context.
func (c *Client) Ping(ctx context.Context) error {
	return c.Client.Ping(ctx).Err()
}