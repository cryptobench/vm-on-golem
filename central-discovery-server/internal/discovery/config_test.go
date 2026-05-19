package discovery

import "testing"

func TestLoadConfigUsesOnlyCanonicalPrefix(t *testing.T) {
	t.Setenv("UNRELATED_DISCOVERY_PORT", "7777")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_PORT", "")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE", "")
	config, err := LoadConfig()
	if err != nil {
		t.Fatal(err)
	}
	if config.Port != 9001 {
		t.Fatalf("expected default port, got %d", config.Port)
	}

	t.Setenv("GOLEM_CENTRAL_DISCOVERY_PORT", "7777")
	config, err = LoadConfig()
	if err != nil {
		t.Fatal(err)
	}
	if config.Port != 7777 {
		t.Fatalf("expected env port, got %d", config.Port)
	}
}

func TestLoadConfigRejectsInvalidValues(t *testing.T) {
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_PORT", "0")
	if _, err := LoadConfig(); err == nil {
		t.Fatal("expected invalid port error")
	}

	t.Setenv("GOLEM_CENTRAL_DISCOVERY_PORT", "9001")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE", "0")
	if _, err := LoadConfig(); err == nil {
		t.Fatal("expected invalid rate limit error")
	}
}

func TestLoadConfigReadsTLSSettings(t *testing.T) {
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_TLS_ENABLED", "true")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP", "94.130.182.147")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_PORT", "8080")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_ACME_DIRECTORY_URL", "https://acme.example.test/directory")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_ACME_PROFILE", "shortlived")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_CERT_DIR", "/tmp/central-certs")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_CERT_RENEW_BEFORE_HOURS", "24")
	t.Setenv("GOLEM_CENTRAL_DISCOVERY_CERT_RENEWAL_CHECK_INTERVAL_SECONDS", "60")

	config, err := LoadConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !config.TLSEnabled {
		t.Fatal("expected TLS enabled")
	}
	if config.PublicIP != "94.130.182.147" {
		t.Fatalf("unexpected public IP: %s", config.PublicIP)
	}
	if config.ACMEHTTPAddress() != "0.0.0.0:8080" {
		t.Fatalf("unexpected ACME HTTP address: %s", config.ACMEHTTPAddress())
	}
	if config.ACMEDirectoryURL != "https://acme.example.test/directory" {
		t.Fatalf("unexpected ACME directory: %s", config.ACMEDirectoryURL)
	}
	if config.ACMEProfile != "shortlived" {
		t.Fatalf("unexpected ACME profile: %s", config.ACMEProfile)
	}
	if config.CertDir != "/tmp/central-certs" {
		t.Fatalf("unexpected cert dir: %s", config.CertDir)
	}
	if config.RenewBeforeHours != 24 || config.RenewCheckSeconds != 60 {
		t.Fatalf("unexpected renewal config: %#v", config)
	}
}
