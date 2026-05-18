package discovery

import (
	"fmt"
	"net"
	"os"
	"strconv"
)

const apiV1Prefix = "/api/v1"

type Config struct {
	Host               string
	Port               int
	Debug              bool
	RateLimitPerMinute int
	ProjectName        string
}

func LoadConfig() (Config, error) {
	config := Config{
		Host:               "0.0.0.0",
		Port:               9001,
		Debug:              false,
		RateLimitPerMinute: 100,
		ProjectName:        "VM on Golem Central Discovery Service",
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

	return config, nil
}

func (c Config) Address() string {
	return net.JoinHostPort(c.Host, strconv.Itoa(c.Port))
}
