package discovery

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

const (
	acmeJWSContentType             = "application/jose+json"
	pemCertificateChainContentType = "application/pem-certificate-chain"
)

type http01ChallengeServer struct {
	address string
	tokens  map[string]string
	server  *http.Server
}

func newHTTP01ChallengeServer(address string) *http01ChallengeServer {
	return &http01ChallengeServer{
		address: address,
		tokens:  map[string]string{},
	}
}

func (s *http01ChallengeServer) setToken(token string, keyAuthorization string) {
	s.tokens[token] = keyAuthorization
}

func (s *http01ChallengeServer) start() error {
	mux := http.NewServeMux()
	mux.HandleFunc("/.well-known/acme-challenge/", func(w http.ResponseWriter, r *http.Request) {
		token := strings.TrimPrefix(r.URL.Path, "/.well-known/acme-challenge/")
		value, ok := s.tokens[token]
		if !ok {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write([]byte(value))
	})
	s.server = &http.Server{
		Addr:              s.address,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}
	listener, err := net.Listen("tcp", s.address)
	if err != nil {
		return err
	}
	go func() {
		if err := s.server.Serve(listener); err != nil && err != http.ErrServerClosed {
			logError("ACME HTTP-01 challenge server stopped: %v", err)
		}
	}()
	return nil
}

func (s *http01ChallengeServer) stop(ctx context.Context) error {
	if s.server == nil {
		return nil
	}
	return s.server.Shutdown(ctx)
}

type nativeACMEClient struct {
	directoryURL    string
	accountKeyPath  string
	certKeyPath     string
	certificatePath string
	email           string
	profile         string
	httpClient      *http.Client
	accountKey      *rsa.PrivateKey
	certKey         *rsa.PrivateKey
	directory       acmeDirectory
	kid             string
}

type acmeDirectory struct {
	NewNonce   string                     `json:"newNonce"`
	NewAccount string                     `json:"newAccount"`
	NewOrder   string                     `json:"newOrder"`
	Meta       map[string]json.RawMessage `json:"meta"`
}

func newNativeACMEClient(config Config) *nativeACMEClient {
	return &nativeACMEClient{
		directoryURL:    config.ACMEDirectoryURL,
		accountKeyPath:  filepath.Join(config.CertDir, "acme-account.key"),
		certKeyPath:     filepath.Join(config.CertDir, "central-discovery-ip.key"),
		certificatePath: filepath.Join(config.CertDir, "central-discovery-ip.crt"),
		email:           config.ACMEAccountEmail,
		profile:         config.ACMEProfile,
		httpClient:      &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *nativeACMEClient) issueIPCertificate(ctx context.Context, ipAddress string, challengeServer *http01ChallengeServer) error {
	var err error
	c.accountKey, err = loadOrCreateRSAKey(c.accountKeyPath)
	if err != nil {
		return err
	}
	c.certKey, err = loadOrCreateRSAKey(c.certKeyPath)
	if err != nil {
		return err
	}
	if err := c.getJSON(ctx, c.directoryURL, &c.directory); err != nil {
		return err
	}
	if err := c.ensureProfileAvailable(); err != nil {
		return err
	}
	if err := c.newAccount(ctx); err != nil {
		return err
	}
	order, err := c.newOrder(ctx, ipAddress)
	if err != nil {
		return err
	}
	if len(order.Authorizations) == 0 {
		return fmt.Errorf("ACME order did not include authorizations")
	}
	if err := c.completeAuthorization(ctx, order.Authorizations[0], challengeServer); err != nil {
		return err
	}
	csr, err := buildIPCSR(c.certKey, ipAddress)
	if err != nil {
		return err
	}
	finalized, err := c.post(ctx, order.Finalize, map[string]string{"csr": b64url(csr)})
	if err != nil {
		return err
	}
	if finalized.OrderURL != "" {
		order.OrderURL = finalized.OrderURL
	}
	order, err = c.pollOrder(ctx, order.OrderURL)
	if err != nil {
		return err
	}
	pemChain, err := c.postAsGetText(ctx, order.Certificate)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(c.certificatePath), 0o700); err != nil {
		return err
	}
	return os.WriteFile(c.certificatePath, []byte(pemChain), 0o644)
}

func (c *nativeACMEClient) getJSON(ctx context.Context, url string, target interface{}) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	response, err := c.httpClient.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode >= 400 {
		body, _ := io.ReadAll(response.Body)
		return fmt.Errorf("ACME GET failed %d: %s", response.StatusCode, strings.TrimSpace(string(body)))
	}
	return json.NewDecoder(response.Body).Decode(target)
}

func (c *nativeACMEClient) newAccount(ctx context.Context) error {
	payload := map[string]interface{}{"termsOfServiceAgreed": true}
	if c.email != "" {
		payload["contact"] = []string{"mailto:" + c.email}
	}
	response, err := c.postJWS(ctx, c.directory.NewAccount, payload, true, "")
	if err != nil {
		return err
	}
	if response.Location == "" {
		return fmt.Errorf("ACME account response did not include Location")
	}
	c.kid = response.Location
	return nil
}

type acmeOrder struct {
	OrderURL       string   `json:"-"`
	Status         string   `json:"status"`
	Authorizations []string `json:"authorizations"`
	Finalize       string   `json:"finalize"`
	Certificate    string   `json:"certificate"`
}

func (c *nativeACMEClient) newOrder(ctx context.Context, ipAddress string) (acmeOrder, error) {
	payload := map[string]interface{}{
		"identifiers": []map[string]string{{"type": "ip", "value": ipAddress}},
	}
	if c.profile != "" {
		payload["profile"] = c.profile
	}
	response, err := c.post(ctx, c.directory.NewOrder, payload)
	if err != nil {
		return acmeOrder{}, err
	}
	if response.Order.OrderURL == "" {
		return acmeOrder{}, fmt.Errorf("ACME order response did not include Location")
	}
	return response.Order, nil
}

type acmeAuthorization struct {
	Status     string          `json:"status"`
	Challenges []acmeChallenge `json:"challenges"`
}

type acmeChallenge struct {
	Type   string `json:"type"`
	URL    string `json:"url"`
	Token  string `json:"token"`
	Status string `json:"status"`
}

func (c *nativeACMEClient) completeAuthorization(ctx context.Context, authorizationURL string, challengeServer *http01ChallengeServer) error {
	var authz acmeAuthorization
	if err := c.postAsGet(ctx, authorizationURL, &authz); err != nil {
		return err
	}
	var challenge *acmeChallenge
	for i := range authz.Challenges {
		if authz.Challenges[i].Type == "http-01" {
			challenge = &authz.Challenges[i]
			break
		}
	}
	if challenge == nil {
		return fmt.Errorf("ACME server did not offer HTTP-01 for IP certificate")
	}
	thumbprint, err := c.jwkThumbprint()
	if err != nil {
		return err
	}
	challengeServer.setToken(challenge.Token, challenge.Token+"."+thumbprint)
	if _, err := c.post(ctx, challenge.URL, map[string]interface{}{}); err != nil {
		return err
	}
	deadline := time.Now().Add(90 * time.Second)
	for time.Now().Before(deadline) {
		if err := waitForPollInterval(ctx); err != nil {
			return err
		}
		if err := c.postAsGet(ctx, authorizationURL, &authz); err != nil {
			return err
		}
		if authz.Status == "valid" {
			return nil
		}
		if authz.Status == "invalid" {
			raw, _ := json.Marshal(authz)
			return fmt.Errorf("ACME authorization failed: %s", raw)
		}
	}
	return fmt.Errorf("timed out waiting for ACME authorization")
}

func (c *nativeACMEClient) pollOrder(ctx context.Context, orderURL string) (acmeOrder, error) {
	deadline := time.Now().Add(90 * time.Second)
	for time.Now().Before(deadline) {
		var order acmeOrder
		if err := c.postAsGet(ctx, orderURL, &order); err != nil {
			return acmeOrder{}, err
		}
		order.OrderURL = orderURL
		if order.Status == "valid" && order.Certificate != "" {
			return order, nil
		}
		if order.Status == "invalid" {
			raw, _ := json.Marshal(order)
			return acmeOrder{}, fmt.Errorf("ACME order failed: %s", raw)
		}
		if err := waitForPollInterval(ctx); err != nil {
			return acmeOrder{}, err
		}
	}
	return acmeOrder{}, fmt.Errorf("timed out waiting for ACME certificate")
}

type acmePostResponse struct {
	Location string
	OrderURL string
	Order    acmeOrder
	Body     []byte
}

func (c *nativeACMEClient) post(ctx context.Context, url string, payload interface{}) (acmePostResponse, error) {
	response, err := c.postJWS(ctx, url, payload, false, "")
	if err != nil {
		return acmePostResponse{}, err
	}
	if len(response.Body) > 0 {
		if err := json.Unmarshal(response.Body, &response.Order); err != nil {
			return acmePostResponse{}, err
		}
	}
	response.Order.OrderURL = response.Location
	response.OrderURL = response.Location
	return response, nil
}

func (c *nativeACMEClient) postAsGet(ctx context.Context, url string, target interface{}) error {
	response, err := c.postJWS(ctx, url, nil, false, "")
	if err != nil {
		return err
	}
	if len(response.Body) == 0 {
		return nil
	}
	return json.Unmarshal(response.Body, target)
}

func (c *nativeACMEClient) postAsGetText(ctx context.Context, url string) (string, error) {
	response, err := c.postJWS(ctx, url, nil, false, pemCertificateChainContentType)
	if err != nil {
		return "", err
	}
	return string(response.Body), nil
}

func (c *nativeACMEClient) postJWS(ctx context.Context, url string, payload interface{}, useJWK bool, accept string) (acmePostResponse, error) {
	body, err := c.jws(ctx, url, payload, useJWK)
	if err != nil {
		return acmePostResponse{}, err
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return acmePostResponse{}, err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(encoded))
	if err != nil {
		return acmePostResponse{}, err
	}
	request.Header.Set("Content-Type", acmeJWSContentType)
	if accept != "" {
		request.Header.Set("Accept", accept)
	}
	response, err := c.httpClient.Do(request)
	if err != nil {
		return acmePostResponse{}, err
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return acmePostResponse{}, err
	}
	if response.StatusCode >= 400 {
		return acmePostResponse{}, fmt.Errorf("ACME request failed %d: %s", response.StatusCode, strings.TrimSpace(string(raw)))
	}
	return acmePostResponse{
		Location: response.Header.Get("Location"),
		Body:     raw,
	}, nil
}

func (c *nativeACMEClient) jws(ctx context.Context, url string, payload interface{}, useJWK bool) (map[string]string, error) {
	if c.accountKey == nil {
		return nil, fmt.Errorf("ACME account key is not initialized")
	}
	protected := map[string]interface{}{
		"alg": "RS256",
		"url": url,
	}
	nonce, err := c.nonce(ctx)
	if err != nil {
		return nil, err
	}
	protected["nonce"] = nonce
	if useJWK {
		protected["jwk"] = c.jwk()
	} else {
		if c.kid == "" {
			return nil, fmt.Errorf("ACME account is not initialized")
		}
		protected["kid"] = c.kid
	}
	protectedJSON, err := json.Marshal(protected)
	if err != nil {
		return nil, err
	}
	protected64 := b64url(protectedJSON)
	payload64 := ""
	if payload != nil {
		payloadJSON, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}
		payload64 = b64url(payloadJSON)
	}
	signingInput := []byte(protected64 + "." + payload64)
	digest := sha256.Sum256(signingInput)
	signature, err := rsa.SignPKCS1v15(rand.Reader, c.accountKey, crypto.SHA256, digest[:])
	if err != nil {
		return nil, err
	}
	return map[string]string{
		"protected": protected64,
		"payload":   payload64,
		"signature": b64url(signature),
	}, nil
}

func (c *nativeACMEClient) nonce(ctx context.Context) (string, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodHead, c.directory.NewNonce, nil)
	if err != nil {
		return "", err
	}
	response, err := c.httpClient.Do(request)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	nonce := response.Header.Get("Replay-Nonce")
	if nonce == "" {
		return "", fmt.Errorf("ACME server did not return a nonce")
	}
	return nonce, nil
}

func (c *nativeACMEClient) jwk() map[string]string {
	numbers := c.accountKey.PublicKey
	return map[string]string{
		"kty": "RSA",
		"n":   b64url(numbers.N.Bytes()),
		"e":   b64url(bigIntBytes(numbers.E)),
	}
}

func (c *nativeACMEClient) jwkThumbprint() (string, error) {
	jwk := c.jwk()
	canonical, err := json.Marshal(map[string]string{
		"e":   jwk["e"],
		"kty": jwk["kty"],
		"n":   jwk["n"],
	})
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(canonical)
	return b64url(digest[:]), nil
}

func (c *nativeACMEClient) ensureProfileAvailable() error {
	if c.profile == "" {
		return nil
	}
	raw, ok := c.directory.Meta["profiles"]
	if !ok {
		return nil
	}
	var profiles map[string]interface{}
	if err := json.Unmarshal(raw, &profiles); err != nil {
		return nil
	}
	if _, ok := profiles[c.profile]; ok {
		return nil
	}
	available := make([]string, 0, len(profiles))
	for profile := range profiles {
		available = append(available, profile)
	}
	sort.Strings(available)
	return fmt.Errorf("configured ACME profile %q is not advertised by the ACME directory; available profiles: %s", c.profile, strings.Join(available, ", "))
}

func b64url(raw []byte) string {
	return base64.RawURLEncoding.EncodeToString(raw)
}

func waitForPollInterval(ctx context.Context) error {
	timer := time.NewTimer(2 * time.Second)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func bigIntBytes(value int) []byte {
	if value == 0 {
		return []byte{0}
	}
	var result []byte
	for value > 0 {
		result = append([]byte{byte(value & 0xff)}, result...)
		value >>= 8
	}
	return result
}

func logError(format string, args ...interface{}) {
	log.Printf(format, args...)
}
