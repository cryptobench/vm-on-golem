package discovery

import (
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"time"
)

const protocolName = "central-discovery.ws.v1"

var ipv4Pattern = regexp.MustCompile(`^(\d{1,3}\.){3}\d{1,3}$`)

type ResourceRequirements struct {
	CPU      *int    `json:"cpu,omitempty"`
	Memory   *int    `json:"memory,omitempty"`
	Storage  *int    `json:"storage,omitempty"`
	Country  *string `json:"country,omitempty"`
	Platform *string `json:"platform,omitempty"`
}

type AdvertisementPayload struct {
	IPAddress        string                 `json:"ip_address"`
	Country          string                 `json:"country"`
	Platform         *string                `json:"platform,omitempty"`
	EndpointProtocol *string                `json:"endpoint_protocol,omitempty"`
	EndpointHost     *string                `json:"endpoint_host,omitempty"`
	EndpointPort     *int                   `json:"endpoint_port,omitempty"`
	EndpointURL      *string                `json:"endpoint_url,omitempty"`
	Resources        map[string]int         `json:"resources"`
	Pricing          map[string]interface{} `json:"pricing,omitempty"`
}

type Advertisement struct {
	AdvertisementPayload
	ProviderID string    `json:"provider_id"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type providerAuthenticateMessage struct {
	Type       string `json:"type"`
	ProviderID string `json:"provider_id"`
	Nonce      string `json:"nonce"`
	Timestamp  string `json:"timestamp"`
	Signature  string `json:"signature"`
}

type providerUpsertMessage struct {
	Type          string               `json:"type"`
	Advertisement AdvertisementPayload `json:"advertisement"`
}

type requestorSubscribeMessage struct {
	Type    string               `json:"type"`
	Filters ResourceRequirements `json:"filters"`
}

func (r ResourceRequirements) Validate() error {
	if err := validatePositive("cpu", r.CPU); err != nil {
		return err
	}
	if err := validatePositive("memory", r.Memory); err != nil {
		return err
	}
	if err := validatePositive("storage", r.Storage); err != nil {
		return err
	}
	if r.Country != nil && len(*r.Country) != 2 {
		return errors.New("country must be exactly 2 characters")
	}
	return nil
}

func (p AdvertisementPayload) Validate() error {
	if !ipv4Pattern.MatchString(p.IPAddress) {
		return errors.New("ip_address must match IPv4 format")
	}
	if len(p.Country) != 2 {
		return errors.New("country must be exactly 2 characters")
	}
	if p.EndpointPort != nil && (*p.EndpointPort < 1 || *p.EndpointPort > 65535) {
		return errors.New("endpoint_port must be 1-65535")
	}
	required := []string{"cpu", "memory", "storage"}
	for _, key := range required {
		value, ok := p.Resources[key]
		if !ok {
			return fmt.Errorf("missing required resources: %s", key)
		}
		if value < 1 {
			return fmt.Errorf("%s must be >= 1", key)
		}
	}
	return nil
}

func decodeMessageType(raw []byte) (string, error) {
	var envelope struct {
		Type string `json:"type"`
	}
	if err := json.Unmarshal(raw, &envelope); err != nil {
		return "", err
	}
	return envelope.Type, nil
}

func validatePositive(name string, value *int) error {
	if value != nil && *value < 1 {
		return fmt.Errorf("%s must be >= 1", name)
	}
	return nil
}
