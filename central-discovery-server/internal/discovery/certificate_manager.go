package discovery

import (
	"context"
	"crypto/tls"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"path/filepath"
	"strings"
	"time"
)

type certificateManager struct {
	config          Config
	certificatePath string
	keyPath         string
	publicIP        string
}

func newCertificateManager(config Config) *certificateManager {
	return &certificateManager{
		config:          config,
		certificatePath: filepath.Join(config.CertDir, "central-discovery-ip.crt"),
		keyPath:         filepath.Join(config.CertDir, "central-discovery-ip.key"),
	}
}

func (m *certificateManager) ensureCertificate(ctx context.Context) error {
	publicIP, err := m.resolvePublicIP(ctx)
	if err != nil {
		return err
	}
	m.publicIP = publicIP
	renewBefore := time.Duration(m.config.RenewBeforeHours) * time.Hour
	result := inspectIPCertificate(m.certificatePath, m.keyPath, publicIP, renewBefore)
	if result.valid {
		log.Printf("Central discovery certificate is valid: %s", result.detail)
		return nil
	}

	if result.renewalDue || !result.usable {
		log.Printf("Central discovery certificate issuance required: %s", result.detail)
		if err := m.issueCertificate(ctx, publicIP); err != nil {
			if result.usable {
				log.Printf("Central discovery certificate renewal failed; continuing with existing certificate: %v", err)
				return nil
			}
			return err
		}
	}

	renewed := inspectIPCertificate(m.certificatePath, m.keyPath, publicIP, renewBefore)
	if !renewed.valid && !renewed.usable {
		return fmt.Errorf("issued certificate is not usable: %s", renewed.detail)
	}
	log.Printf("Central discovery certificate ready: %s", renewed.detail)
	return nil
}

func (m *certificateManager) startRenewalLoop(ctx context.Context) {
	interval := time.Duration(m.config.RenewCheckSeconds) * time.Second
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := m.ensureCertificate(ctx); err != nil {
				log.Printf("Central discovery certificate renewal check failed: %v", err)
			}
		}
	}
}

func (m *certificateManager) getCertificate(_ *tls.ClientHelloInfo) (*tls.Certificate, error) {
	cert, err := tls.LoadX509KeyPair(m.certificatePath, m.keyPath)
	if err != nil {
		return nil, err
	}
	return &cert, nil
}

func (m *certificateManager) issueCertificate(ctx context.Context, publicIP string) error {
	challengeServer := newHTTP01ChallengeServer(m.config.ACMEHTTPAddress())
	if err := challengeServer.start(); err != nil {
		return err
	}
	defer func() {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := challengeServer.stop(shutdownCtx); err != nil {
			log.Printf("Central discovery ACME challenge server shutdown failed: %v", err)
		}
	}()

	client := newNativeACMEClient(m.config)
	return client.issueIPCertificate(ctx, publicIP, challengeServer)
}

func (m *certificateManager) resolvePublicIP(ctx context.Context) (string, error) {
	configured := strings.TrimSpace(m.config.PublicIP)
	if configured != "" && configured != "auto" {
		if net.ParseIP(configured) == nil {
			return "", fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP is not a valid IP address")
		}
		return configured, nil
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, m.config.PublicIPLookupURL, nil)
	if err != nil {
		return "", err
	}
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	if response.StatusCode >= 400 {
		return "", fmt.Errorf("public IP lookup failed with status %d", response.StatusCode)
	}
	raw, err := io.ReadAll(io.LimitReader(response.Body, 128))
	if err != nil {
		return "", err
	}
	publicIP := strings.TrimSpace(string(raw))
	if net.ParseIP(publicIP) == nil {
		return "", fmt.Errorf("public IP lookup returned invalid IP address %q", publicIP)
	}
	return publicIP, nil
}
