package discovery

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
)

const apiV1Prefix = "/api/v1"

type Config struct {
	Host                       string
	Port                       int
	Debug                      bool
	RateLimitPerMinute         int
	ProjectName                string
	PortCheckRetries           int
	PortCheckRetryDelaySeconds float64
	PortCheckTimeoutSeconds    float64
	TLSEnabled                 bool
	PublicIP                   string
	PublicIPLookupURL          string
	ACMEHTTPHost               string
	ACMEHTTPPort               int
	ACMEDirectoryURL           string
	ACMEProfile                string
	ACMEAccountEmail           string
	CertDir                    string
	RenewBeforeHours           int
	RenewCheckSeconds          int
}

func LoadConfig() (Config, error) {
	config := Config{
		Host:                       "0.0.0.0",
		Port:                       9001,
		Debug:                      false,
		RateLimitPerMinute:         100,
		ProjectName:                "VM on Golem Central Discovery Service",
		PortCheckRetries:           1,
		PortCheckRetryDelaySeconds: 0.25,
		PortCheckTimeoutSeconds:    3,
		TLSEnabled:                 false,
		PublicIP:                   "auto",
		PublicIPLookupURL:          "https://api.ipify.org",
		ACMEHTTPHost:               "0.0.0.0",
		ACMEHTTPPort:               80,
		ACMEDirectoryURL:           "https://acme-v02.api.letsencrypt.org/directory",
		ACMEProfile:                "shortlived",
		ACMEAccountEmail:           "",
		CertDir:                    defaultCertDir(),
		RenewBeforeHours:           48,
		RenewCheckSeconds:          3600,
	}

	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_HOST"); value != "" {
		config.Host = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PORT"); value != "" {
		port, err := strconv.Atoi(value)
		if err != nil || port < 1 || port > 65535 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_PORT must be 1-65535")
		}
		config.Port = port
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_DEBUG"); value != "" {
		debug, err := strconv.ParseBool(value)
		if err != nil {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_DEBUG must be a boolean")
		}
		config.Debug = debug
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE"); value != "" {
		limit, err := strconv.Atoi(value)
		if err != nil || limit < 1 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_RATE_LIMIT_PER_MINUTE must be >= 1")
		}
		config.RateLimitPerMinute = limit
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRIES"); value != "" {
		retries, err := strconv.Atoi(value)
		if err != nil || retries < 1 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRIES must be >= 1")
		}
		config.PortCheckRetries = retries
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRY_DELAY_SECONDS"); value != "" {
		seconds, err := strconv.ParseFloat(value, 64)
		if err != nil || seconds < 0 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_RETRY_DELAY_SECONDS must be >= 0")
		}
		config.PortCheckRetryDelaySeconds = seconds
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_TIMEOUT_SECONDS"); value != "" {
		seconds, err := strconv.ParseFloat(value, 64)
		if err != nil || seconds <= 0 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_PORT_CHECK_TIMEOUT_SECONDS must be > 0")
		}
		config.PortCheckTimeoutSeconds = seconds
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_TLS_ENABLED"); value != "" {
		enabled, err := strconv.ParseBool(value)
		if err != nil {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_TLS_ENABLED must be a boolean")
		}
		config.TLSEnabled = enabled
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP"); value != "" {
		config.PublicIP = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_PUBLIC_IP_LOOKUP_URL"); value != "" {
		config.PublicIPLookupURL = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_HOST"); value != "" {
		config.ACMEHTTPHost = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_PORT"); value != "" {
		port, err := strconv.Atoi(value)
		if err != nil || port < 1 || port > 65535 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_ACME_HTTP_PORT must be 1-65535")
		}
		config.ACMEHTTPPort = port
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_ACME_DIRECTORY_URL"); value != "" {
		config.ACMEDirectoryURL = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_ACME_PROFILE"); value != "" {
		config.ACMEProfile = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_ACME_ACCOUNT_EMAIL"); value != "" {
		config.ACMEAccountEmail = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_CERT_DIR"); value != "" {
		config.CertDir = value
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_CERT_RENEW_BEFORE_HOURS"); value != "" {
		hours, err := strconv.Atoi(value)
		if err != nil || hours < 1 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_CERT_RENEW_BEFORE_HOURS must be >= 1")
		}
		config.RenewBeforeHours = hours
	}
	if value := os.Getenv("GOLEM_CENTRAL_DISCOVERY_CERT_RENEWAL_CHECK_INTERVAL_SECONDS"); value != "" {
		seconds, err := strconv.Atoi(value)
		if err != nil || seconds < 1 {
			return Config{}, fmt.Errorf("GOLEM_CENTRAL_DISCOVERY_CERT_RENEWAL_CHECK_INTERVAL_SECONDS must be >= 1")
		}
		config.RenewCheckSeconds = seconds
	}

	return config, nil
}

func (c Config) Address() string {
	return net.JoinHostPort(c.Host, strconv.Itoa(c.Port))
}

func (c Config) ACMEHTTPAddress() string {
	return net.JoinHostPort(c.ACMEHTTPHost, strconv.Itoa(c.ACMEHTTPPort))
}

func defaultCertDir() string {
	home, err := os.UserHomeDir()
	if err != nil || home == "" {
		return ".golem-central-discovery-certs"
	}
	return filepath.Join(home, ".golem", "central-discovery", "certs")
}
