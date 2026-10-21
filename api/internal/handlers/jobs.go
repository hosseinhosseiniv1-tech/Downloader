package handlers

import (
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"

	"github.com/super-downloader/api/internal/jobs"
)

// listJobsHandler serves GET /api/v1/jobs with pagination + filters.
func (d *Deps) listJobsHandler(c *gin.Context) {
	f := jobs.JobFilter{
		Status:   c.Query("status"),
		Platform: c.Query("platform"),
	}
	if v := c.Query("page"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			f.Page = n
		}
	}
	if v := c.Query("per_page"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			f.PerPage = n
		}
	}
	if v := c.Query("from"); v != "" {
		if t, err := time.Parse(time.RFC3339, v); err == nil {
			f.From = t
		}
	}
	if v := c.Query("to"); v != "" {
		if t, err := time.Parse(time.RFC3339, v); err == nil {
			f.To = t
		}
	}

	reader := jobs.New(d.Redis)
	resp, err := reader.ListJobs(c.Request.Context(), f)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "jobs_unavailable"})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// getJobHandler serves GET /api/v1/jobs/:id.
func (d *Deps) getJobHandler(c *gin.Context) {
	id := c.Param("id")
	reader := jobs.New(d.Redis)
	job, err := reader.GetJob(c.Request.Context(), id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "job_unavailable"})
		return
	}
	if job == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "not_found"})
		return
	}
	c.JSON(http.StatusOK, job)
}