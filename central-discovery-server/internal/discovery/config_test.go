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
