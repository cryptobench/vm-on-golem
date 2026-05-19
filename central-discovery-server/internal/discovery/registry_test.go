package discovery

import "testing"

func TestRegistrySnapshotFiltersAdvertisements(t *testing.T) {
	registry := NewRegistry()
	platform := "arm64"
	registry.UpsertProvider("provider-a", AdvertisementPayload{
		IPAddress: "1.2.3.4",
		Country:   "US",
		Platform:  &platform,
		Resources: map[string]int{"cpu": 4, "memory": 8, "storage": 20},
	})
	registry.UpsertProvider("provider-b", AdvertisementPayload{
		IPAddress: "1.2.3.5",
		Country:   "SE",
		Platform:  &platform,
		Resources: map[string]int{"cpu": 1, "memory": 8, "storage": 20},
	})

	cpu := 2
	country := "us"
	matching := registry.Snapshot(ResourceRequirements{CPU: &cpu, Country: &country})
	if len(matching) != 1 {
		t.Fatalf("expected one match, got %d", len(matching))
	}
	if matching[0].ProviderID != "provider-a" {
		t.Fatalf("unexpected provider %s", matching[0].ProviderID)
	}

	if removed := registry.RemoveProvider("provider-a"); !removed {
		t.Fatal("expected provider to be removed")
	}
	if len(registry.Snapshot(ResourceRequirements{})) != 1 {
		t.Fatal("expected one provider after removal")
	}
}

func TestAdvertisementValidationRequiresResources(t *testing.T) {
	payload := AdvertisementPayload{
		IPAddress: "1.2.3.4",
		Country:   "US",
		Resources: map[string]int{"cpu": 1, "memory": 1},
	}
	if err := payload.Validate(); err == nil {
		t.Fatal("expected missing storage error")
	}

	payload.Resources = map[string]int{"cpu": 1, "memory": 1, "storage": 0}
	if err := payload.Validate(); err == nil {
		t.Fatal("expected invalid storage error")
	}
}
