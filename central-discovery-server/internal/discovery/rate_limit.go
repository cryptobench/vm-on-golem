package discovery

import (
	"net"
	"net/http"
	"strings"
	"sync"
	"time"
)

type rateLimitMiddleware struct {
	next              http.Handler
	requestsPerMinute int
	mu                sync.Mutex
	requests          map[string][]time.Time
}

func newRateLimitMiddleware(next http.Handler, requestsPerMinute int) http.Handler {
	return &rateLimitMiddleware{
		next:              next,
		requestsPerMinute: requestsPerMinute,
		requests:          make(map[string][]time.Time),
	}
}

func (m *rateLimitMiddleware) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		m.next.ServeHTTP(w, r)
		return
	}

	clientIP := clientIP(r)
	now := utcNow()
	if !m.allow(clientIP, now) {
		writeJSON(w, http.StatusTooManyRequests, map[string]string{"detail": "Rate limit exceeded"})
		return
	}
	m.next.ServeHTTP(w, r)
}

func (m *rateLimitMiddleware) allow(clientIP string, now time.Time) bool {
	m.mu.Lock()
	defer m.mu.Unlock()

	cutoff := now.Add(-time.Minute)
	recent := m.requests[clientIP][:0]
	for _, timestamp := range m.requests[clientIP] {
		if timestamp.After(cutoff) {
			recent = append(recent, timestamp)
		}
	}
	if len(recent) >= m.requestsPerMinute {
		m.requests[clientIP] = recent
		return false
	}
	m.requests[clientIP] = append(recent, now)
	return true
}

func clientIP(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err == nil && host != "" {
		return host
	}
	if r.RemoteAddr != "" {
		return r.RemoteAddr
	}
	return "unknown"
}
