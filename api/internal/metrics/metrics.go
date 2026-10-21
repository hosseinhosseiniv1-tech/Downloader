package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Metrics is a container for all Prometheus collectors exposed by the API.
type Metrics struct {
	APIRequests       *prometheus.CounterVec
	APIDuration       *prometheus.HistogramVec
	JobsQueued        prometheus.Counter
	JobsCompleted     prometheus.Counter
	JobsFailed        prometheus.Counter
	UploadFailures    prometheus.Counter
	DownloadBytes     prometheus.Counter
}

// New registers (idempotently) every metric with the default registry.
func New() *Metrics {
	return &Metrics{
		APIRequests: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "api_requests_total",
			Help: "Total HTTP requests served, labelled by route and status.",
		}, []string{"route", "method", "status"}),
		APIDuration: promauto.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "api_request_duration_seconds",
			Help:    "HTTP request duration in seconds.",
			Buckets: prometheus.DefBuckets,
		}, []string{"route", "method"}),
		JobsQueued: promauto.NewCounter(prometheus.CounterOpts{
			Name: "jobs_queued_total",
			Help: "Total jobs enqueued by this API instance.",
		}),
		JobsCompleted: promauto.NewCounter(prometheus.CounterOpts{
			Name: "jobs_completed_total",
			Help: "Total jobs completed (mirrors worker metric).",
		}),
		JobsFailed: promauto.NewCounter(prometheus.CounterOpts{
			Name: "jobs_failed_total",
			Help: "Total jobs that failed (mirrors worker metric).",
		}),
		UploadFailures: promauto.NewCounter(prometheus.CounterOpts{
			Name: "upload_failures_total",
			Help: "Total upload failures, including 2 GB limit hits.",
		}),
		DownloadBytes: promauto.NewCounter(prometheus.CounterOpts{
			Name: "download_bytes_total",
			Help: "Total bytes downloaded (mirrors worker metric).",
		}),
	}
}