package discovery

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"
)

type dialContext func(context.Context, string, string) (net.Conn, error)

type PortChecker struct {
	retries     int
	retryDelay  time.Duration
	timeout     time.Duration
	dialContext dialContext
	tlsConfig   *tls.Config
}

type portCheckRequest struct {
	ProviderIP string `json:"provider_ip"`
	Ports      []int  `json:"ports"`
}

type portStatus struct {
	Accessible bool    `json:"accessible"`
	Error      *string `json:"error"`
}

type portCheckResponse struct {
	Success bool               `json:"success"`
	Results map[int]portStatus `json:"results"`
	Message string             `json:"message"`
}

type tlsCheckRequest struct {
	Host       string `json:"host"`
	Port       int    `json:"port"`
	ExpectedIP string `json:"expected_ip,omitempty"`
}

type tlsCheckResponse struct {
	Valid    bool    `json:"valid"`
	Error    *string `json:"error"`
	Peer     string  `json:"peer"`
	NotAfter *string `json:"not_after"`
}

func newPortChecker(config Config) *PortChecker {
	dialer := &net.Dialer{Timeout: secondsDuration(config.PortCheckTimeoutSeconds)}
	return &PortChecker{
		retries:     config.PortCheckRetries,
		retryDelay:  secondsDuration(config.PortCheckRetryDelaySeconds),
		timeout:     secondsDuration(config.PortCheckTimeoutSeconds),
		dialContext: dialer.DialContext,
	}
}

func secondsDuration(seconds float64) time.Duration {
	return time.Duration(seconds * float64(time.Second))
}

func (s *Server) checkPorts(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"detail": "method not allowed"})
		return
	}

	var request portCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"detail": "invalid JSON body"})
		return
	}
	if err := request.validate(); err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"detail": err.Error()})
		return
	}

	startedAt := time.Now()
	results := s.portChecker.CheckPorts(r.Context(), request.ProviderIP, request.Ports)
	accessible := 0
	for _, result := range results {
		if result.Accessible {
			accessible++
		}
	}
	message := fmt.Sprintf("Successfully verified %d out of %d ports", accessible, len(request.Ports))
	log.Printf("Port check summary: %s elapsed=%s", message, time.Since(startedAt).Round(time.Millisecond))
	writeJSON(w, http.StatusOK, portCheckResponse{
		Success: accessible > 0,
		Results: results,
		Message: message,
	})
}

func (s *Server) checkTLS(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"detail": "method not allowed"})
		return
	}

	var request tlsCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"detail": "invalid JSON body"})
		return
	}
	if err := request.validate(); err != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"detail": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, s.portChecker.CheckTLS(r.Context(), request))
}

func (r portCheckRequest) validate() error {
	if strings.TrimSpace(r.ProviderIP) == "" {
		return errors.New("provider_ip is required")
	}
	if len(r.Ports) == 0 {
		return errors.New("ports must not be empty")
	}
	for _, port := range r.Ports {
		if port < 1 || port > 65535 {
			return fmt.Errorf("Invalid port number: %d", port)
		}
	}
	return nil
}

func (r tlsCheckRequest) validate() error {
	if strings.TrimSpace(r.Host) == "" {
		return errors.New("host is required")
	}
	if r.Port < 1 || r.Port > 65535 {
		return fmt.Errorf("Invalid port number: %d", r.Port)
	}
	if r.ExpectedIP != "" {
		if parsed := net.ParseIP(r.ExpectedIP); parsed == nil {
			return fmt.Errorf("expected_ip must be an IP address")
		}
	}
	return nil
}

func (p *PortChecker) CheckPorts(ctx context.Context, host string, ports []int) map[int]portStatus {
	results := make(map[int]portStatus, len(ports))
	var mu sync.Mutex
	var wg sync.WaitGroup
	for _, port := range ports {
		port := port
		wg.Add(1)
		go func() {
			defer wg.Done()
			result := p.CheckPort(ctx, host, port)
			mu.Lock()
			results[port] = result
			mu.Unlock()
		}()
	}
	wg.Wait()
	return results
}

func (p *PortChecker) CheckPort(ctx context.Context, host string, port int) portStatus {
	var lastError string
	for attempt := 0; attempt < p.retries; attempt++ {
		attemptCtx, cancel := context.WithTimeout(ctx, p.timeout)
		conn, err := p.dialContext(attemptCtx, "tcp", net.JoinHostPort(host, fmt.Sprintf("%d", port)))
		cancel()
		if err == nil {
			_ = conn.Close()
			return portStatus{Accessible: true, Error: nil}
		}
		lastError = normalizeDialError(err)
		if attempt < p.retries-1 {
			select {
			case <-ctx.Done():
				errText := normalizeDialError(ctx.Err())
				return portStatus{Accessible: false, Error: &errText}
			case <-time.After(p.retryDelay):
			}
		}
	}
	return portStatus{Accessible: false, Error: &lastError}
}

func (p *PortChecker) CheckTLS(ctx context.Context, request tlsCheckRequest) tlsCheckResponse {
	peer := net.JoinHostPort(request.Host, fmt.Sprintf("%d", request.Port))
	baseConfig := &tls.Config{}
	if p.tlsConfig != nil {
		baseConfig = p.tlsConfig.Clone()
	}
	baseConfig.ServerName = request.Host
	dialer := &tls.Dialer{
		NetDialer: &net.Dialer{Timeout: p.timeout},
		Config:    baseConfig,
	}
	attemptCtx, cancel := context.WithTimeout(ctx, p.timeout)
	conn, err := dialer.DialContext(attemptCtx, "tcp", peer)
	cancel()
	if err != nil {
		errText := err.Error()
		log.Printf("TLS check failed for %s: %s", peer, errText)
		return tlsCheckResponse{Valid: false, Error: &errText, Peer: peer}
	}
	defer conn.Close()

	tlsConn, ok := conn.(*tls.Conn)
	if !ok {
		errText := "connection did not negotiate TLS"
		return tlsCheckResponse{Valid: false, Error: &errText, Peer: peer}
	}
	state := tlsConn.ConnectionState()
	if len(state.PeerCertificates) == 0 {
		errText := "no certificate"
		return tlsCheckResponse{Valid: false, Error: &errText, Peer: peer}
	}
	cert := state.PeerCertificates[0]
	notAfter := cert.NotAfter.UTC().Format(time.RFC3339)
	if !cert.NotAfter.After(utcNow()) {
		errText := "certificate expired"
		return tlsCheckResponse{Valid: false, Error: &errText, Peer: peer, NotAfter: &notAfter}
	}
	if request.ExpectedIP != "" {
		expectedIP := net.ParseIP(request.ExpectedIP)
		matched := false
		for _, certIP := range cert.IPAddresses {
			if certIP.Equal(expectedIP) {
				matched = true
				break
			}
		}
		if !matched {
			errText := "certificate does not match expected IP"
			return tlsCheckResponse{Valid: false, Error: &errText, Peer: peer, NotAfter: &notAfter}
		}
	}
	return tlsCheckResponse{Valid: true, Error: nil, Peer: peer, NotAfter: &notAfter}
}

func normalizeDialError(err error) string {
	if err == nil {
		return ""
	}
	if errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled) {
		return "Connection timed out"
	}
	text := err.Error()
	if strings.Contains(strings.ToLower(text), "connection refused") {
		return "Connection refused"
	}
	return text
}
