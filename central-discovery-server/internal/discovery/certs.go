package discovery

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"time"
)

type certificateValidation struct {
	usable     bool
	valid      bool
	renewalDue bool
	detail     string
	expiresAt  time.Time
}

func loadOrCreateRSAKey(path string) (*rsa.PrivateKey, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	if raw, err := os.ReadFile(path); err == nil {
		return parseRSAKey(raw, path)
	}
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}
	raw := pem.EncodeToMemory(&pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(key),
	})
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		return nil, err
	}
	return key, nil
}

func loadRSAKey(path string) (*rsa.PrivateKey, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseRSAKey(raw, path)
}

func parseRSAKey(raw []byte, path string) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode(raw)
	if block == nil {
		return nil, fmt.Errorf("invalid private key PEM at %s", path)
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	key, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("private key at %s is not RSA", path)
	}
	return key, nil
}

func buildIPCSR(key crypto.Signer, ipAddress string) ([]byte, error) {
	ip := net.ParseIP(ipAddress)
	if ip == nil {
		return nil, fmt.Errorf("invalid IP address %q", ipAddress)
	}
	return x509.CreateCertificateRequest(rand.Reader, &x509.CertificateRequest{
		Subject:     pkix.Name{},
		IPAddresses: []net.IP{ip},
	}, key)
}

func inspectIPCertificate(certPath string, keyPath string, ipAddress string, renewBefore time.Duration) certificateValidation {
	certPEM, err := os.ReadFile(certPath)
	if err != nil {
		return certificateValidation{detail: "missing certificate"}
	}
	key, err := loadRSAKey(keyPath)
	if err != nil {
		return certificateValidation{detail: err.Error()}
	}
	block, _ := pem.Decode(certPEM)
	if block == nil {
		return certificateValidation{detail: "invalid certificate PEM"}
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return certificateValidation{detail: err.Error()}
	}
	certKey, ok := cert.PublicKey.(*rsa.PublicKey)
	if !ok {
		return certificateValidation{detail: "certificate public key is not RSA"}
	}
	if certKey.N.Cmp(key.PublicKey.N) != 0 || certKey.E != key.PublicKey.E {
		return certificateValidation{detail: "certificate key does not match"}
	}
	ip := net.ParseIP(ipAddress)
	if ip == nil {
		return certificateValidation{detail: "invalid public IP"}
	}
	matchesIP := false
	for _, candidate := range cert.IPAddresses {
		if candidate.Equal(ip) {
			matchesIP = true
			break
		}
	}
	if !matchesIP {
		return certificateValidation{detail: "certificate does not match public IP"}
	}
	now := utcNow()
	expiresAt := cert.NotAfter
	if expiresAt.Location() != time.UTC {
		expiresAt = expiresAt.UTC()
	}
	if !expiresAt.After(now) {
		return certificateValidation{detail: "certificate expired", expiresAt: expiresAt}
	}
	if expiresAt.Before(now.Add(renewBefore)) {
		return certificateValidation{
			usable:     true,
			renewalDue: true,
			detail:     "certificate renewal required",
			expiresAt:  expiresAt,
		}
	}
	return certificateValidation{
		usable:    true,
		valid:     true,
		detail:    fmt.Sprintf("valid until %s", expiresAt.Format(time.RFC3339)),
		expiresAt: expiresAt,
	}
}
