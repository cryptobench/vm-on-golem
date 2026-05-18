package discovery

import (
	"crypto/ecdsa"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/crypto"
	"github.com/gorilla/websocket"
)

func TestHealthEndpoint(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	response, err := http.Get(testServer.URL + "/health")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.StatusCode)
	}
}

func TestProviderAuthRejectsWrongSignature(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	provider := dialWebsocket(t, testServer, "/api/v1/discovery/providers")
	defer provider.Close()

	hello := readEvent(t, provider)
	providerID := testProviderID(t)
	writeJSONMessage(t, provider, map[string]interface{}{
		"type":        "authenticate",
		"provider_id": providerID,
		"nonce":       hello["nonce"],
		"timestamp":   utcNow().Format(time.RFC3339Nano),
		"signature":   "0x" + strings.Repeat("00", 65),
	})

	errEvent := readEvent(t, provider)
	if errEvent["type"] != "error" || !strings.Contains(errEvent["error"].(string), "signature") {
		t.Fatalf("unexpected error event: %#v", errEvent)
	}
}

func TestProviderAuthRejectsExpiredTimestamp(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	provider := dialWebsocket(t, testServer, "/api/v1/discovery/providers")
	defer provider.Close()

	hello := readEvent(t, provider)
	privateKey := testPrivateKey(t)
	providerID := crypto.PubkeyToAddress(privateKey.PublicKey).Hex()
	timestamp := utcNow().Add(-10 * time.Minute).Format(time.RFC3339Nano)
	writeJSONMessage(t, provider, map[string]interface{}{
		"type":        "authenticate",
		"provider_id": providerID,
		"nonce":       hello["nonce"],
		"timestamp":   timestamp,
		"signature":   signAuthForTest(t, privateKey, providerID, hello["nonce"].(string), timestamp),
	})

	errEvent := readEvent(t, provider)
	if errEvent["type"] != "error" || !strings.Contains(errEvent["error"].(string), "expired") {
		t.Fatalf("unexpected error event: %#v", errEvent)
	}
}

func TestProviderUpsertSnapshotRemoveAndDisconnect(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	requestor := dialWebsocket(t, testServer, "/api/v1/discovery/requestors")
	defer requestor.Close()
	if readEvent(t, requestor)["type"] != "hello" {
		t.Fatal("expected requestor hello")
	}
	writeJSONMessage(t, requestor, map[string]interface{}{
		"type":    "subscribe",
		"filters": map[string]interface{}{"cpu": 2},
	})
	snapshot := readEvent(t, requestor)
	if snapshot["type"] != "snapshot" || len(snapshot["advertisements"].([]interface{})) != 0 {
		t.Fatalf("unexpected snapshot: %#v", snapshot)
	}

	provider := authenticatedProvider(t, testServer)
	writeJSONMessage(t, provider, map[string]interface{}{
		"type":          "advertisement.upsert",
		"advertisement": advertisementForTest(4, "SE"),
	})
	accepted := readEvent(t, provider)
	if accepted["type"] != "advertisement.accepted" {
		t.Fatalf("unexpected accepted event: %#v", accepted)
	}
	update := readEvent(t, requestor)
	if update["type"] != "provider.upsert" {
		t.Fatalf("unexpected update: %#v", update)
	}
	advertisement := update["advertisement"].(map[string]interface{})
	if advertisement["provider_id"] != testProviderID(t) {
		t.Fatalf("unexpected provider id: %#v", advertisement["provider_id"])
	}

	writeJSONMessage(t, provider, map[string]interface{}{
		"type":          "advertisement.upsert",
		"advertisement": advertisementForTest(1, "SE"),
	})
	if readEvent(t, provider)["type"] != "advertisement.accepted" {
		t.Fatal("expected accepted event")
	}
	removed := readEvent(t, requestor)
	if removed["type"] != "provider.remove" || removed["provider_id"] != testProviderID(t) {
		t.Fatalf("unexpected remove event: %#v", removed)
	}

	writeJSONMessage(t, provider, map[string]interface{}{
		"type":          "advertisement.upsert",
		"advertisement": advertisementForTest(3, "SE"),
	})
	if readEvent(t, provider)["type"] != "advertisement.accepted" {
		t.Fatal("expected accepted event")
	}
	if readEvent(t, requestor)["type"] != "provider.upsert" {
		t.Fatal("expected provider upsert")
	}
	provider.Close()
	disconnected := readEvent(t, requestor)
	if disconnected["type"] != "provider.remove" || disconnected["provider_id"] != testProviderID(t) {
		t.Fatalf("unexpected disconnect event: %#v", disconnected)
	}
}

func TestRequestorFilterSnapshotContainsOnlyMatchingConnectedProviders(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	provider := authenticatedProvider(t, testServer)
	defer provider.Close()
	writeJSONMessage(t, provider, map[string]interface{}{
		"type":          "advertisement.upsert",
		"advertisement": advertisementForTest(2, "US"),
	})
	if readEvent(t, provider)["type"] != "advertisement.accepted" {
		t.Fatal("expected accepted event")
	}

	requestor := dialWebsocket(t, testServer, "/api/v1/discovery/requestors")
	defer requestor.Close()
	readEvent(t, requestor)
	writeJSONMessage(t, requestor, map[string]interface{}{
		"type":    "subscribe",
		"filters": map[string]interface{}{"country": "SE"},
	})
	if len(readEvent(t, requestor)["advertisements"].([]interface{})) != 0 {
		t.Fatal("expected no SE providers")
	}

	writeJSONMessage(t, requestor, map[string]interface{}{
		"type":    "subscribe",
		"filters": map[string]interface{}{"country": "US"},
	})
	snapshot := readEvent(t, requestor)
	if len(snapshot["advertisements"].([]interface{})) != 1 {
		t.Fatalf("expected one US provider: %#v", snapshot)
	}
}

func TestInvalidProviderMessageClosesWithError(t *testing.T) {
	testServer := httptest.NewServer(NewServer(testConfig()).Handler())
	defer testServer.Close()

	provider := authenticatedProvider(t, testServer)
	defer provider.Close()
	writeJSONMessage(t, provider, map[string]interface{}{"type": "unknown"})

	errEvent := readEvent(t, provider)
	if errEvent["type"] != "error" || !strings.Contains(errEvent["error"].(string), "unsupported provider message type") {
		t.Fatalf("unexpected error event: %#v", errEvent)
	}
}

func authenticatedProvider(t *testing.T, testServer *httptest.Server) *websocket.Conn {
	t.Helper()
	provider := dialWebsocket(t, testServer, "/api/v1/discovery/providers")
	hello := readEvent(t, provider)
	privateKey := testPrivateKey(t)
	providerID := crypto.PubkeyToAddress(privateKey.PublicKey).Hex()
	timestamp := utcNow().Format(time.RFC3339Nano)
	writeJSONMessage(t, provider, map[string]interface{}{
		"type":        "authenticate",
		"provider_id": providerID,
		"nonce":       hello["nonce"],
		"timestamp":   timestamp,
		"signature":   signAuthForTest(t, privateKey, providerID, hello["nonce"].(string), timestamp),
	})
	response := readEvent(t, provider)
	if response["type"] != "authenticated" {
		t.Fatalf("expected authenticated, got %#v", response)
	}
	return provider
}

func dialWebsocket(t *testing.T, testServer *httptest.Server, path string) *websocket.Conn {
	t.Helper()
	url := "ws" + strings.TrimPrefix(testServer.URL, "http") + path
	conn, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		t.Fatal(err)
	}
	return conn
}

func readEvent(t *testing.T, conn *websocket.Conn) map[string]interface{} {
	t.Helper()
	_, raw, err := conn.ReadMessage()
	if err != nil {
		t.Fatal(err)
	}
	var event map[string]interface{}
	if err := json.Unmarshal(raw, &event); err != nil {
		t.Fatal(err)
	}
	return event
}

func writeJSONMessage(t *testing.T, conn *websocket.Conn, message interface{}) {
	t.Helper()
	if err := conn.WriteJSON(message); err != nil {
		t.Fatal(err)
	}
}

func signAuthForTest(t *testing.T, privateKey *ecdsa.PrivateKey, providerID string, nonce string, timestamp string) string {
	t.Helper()
	hash := personalSignHash(providerAuthMessage(providerID, nonce, timestamp))
	signature, err := crypto.Sign(hash, privateKey)
	if err != nil {
		t.Fatal(err)
	}
	signature[64] += 27
	return "0x" + hex.EncodeToString(signature)
}

func testPrivateKey(t *testing.T) *ecdsa.PrivateKey {
	t.Helper()
	privateKey, err := crypto.HexToECDSA("1111111111111111111111111111111111111111111111111111111111111111")
	if err != nil {
		t.Fatal(err)
	}
	return privateKey
}

func testProviderID(t *testing.T) string {
	t.Helper()
	privateKey := testPrivateKey(t)
	return crypto.PubkeyToAddress(privateKey.PublicKey).Hex()
}

func advertisementForTest(cpu int, country string) map[string]interface{} {
	return map[string]interface{}{
		"ip_address":        "1.2.3.4",
		"country":           country,
		"platform":          "arm64",
		"endpoint_protocol": "https",
		"endpoint_host":     "provider.example",
		"endpoint_port":     443,
		"endpoint_url":      "https://provider.example",
		"resources": map[string]interface{}{
			"cpu":     cpu,
			"memory":  4,
			"storage": 10,
		},
		"pricing": map[string]interface{}{
			"usd_per_core_month":       6.0,
			"usd_per_gb_ram_month":     2.5,
			"usd_per_gb_storage_month": 0.12,
			"glm_per_core_month":       12.0,
			"glm_per_gb_ram_month":     5.0,
			"glm_per_gb_storage_month": 0.24,
		},
	}
}

func testConfig() Config {
	return Config{
		Host:               "127.0.0.1",
		Port:               9001,
		RateLimitPerMinute: 100,
		ProjectName:        "VM on Golem Central Discovery Service",
	}
}
