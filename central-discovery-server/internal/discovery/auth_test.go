package discovery

import (
	"testing"
	"time"

	"github.com/ethereum/go-ethereum/crypto"
)

func TestVerifyProviderAuthRecoversPersonalSignAddress(t *testing.T) {
	privateKey, err := crypto.HexToECDSA("1111111111111111111111111111111111111111111111111111111111111111")
	if err != nil {
		t.Fatal(err)
	}
	providerID := crypto.PubkeyToAddress(privateKey.PublicKey).Hex()
	nonce := "nonce"
	timestamp := utcNow().Format(time.RFC3339Nano)
	signature := signAuthForTest(t, privateKey, providerID, nonce, timestamp)

	recovered, err := verifyProviderAuth(providerAuthenticateMessage{
		Type:       "authenticate",
		ProviderID: providerID,
		Nonce:      nonce,
		Timestamp:  timestamp,
		Signature:  signature,
	}, nonce)
	if err != nil {
		t.Fatal(err)
	}
	if recovered != providerID {
		t.Fatalf("expected %s, got %s", providerID, recovered)
	}
}

func TestVerifyProviderAuthRejectsExpiredTimestamp(t *testing.T) {
	privateKey, err := crypto.HexToECDSA("1111111111111111111111111111111111111111111111111111111111111111")
	if err != nil {
		t.Fatal(err)
	}
	providerID := crypto.PubkeyToAddress(privateKey.PublicKey).Hex()
	nonce := "nonce"
	timestamp := utcNow().Add(-10 * time.Minute).Format(time.RFC3339Nano)
	signature := signAuthForTest(t, privateKey, providerID, nonce, timestamp)

	_, err = verifyProviderAuth(providerAuthenticateMessage{
		Type:       "authenticate",
		ProviderID: providerID,
		Nonce:      nonce,
		Timestamp:  timestamp,
		Signature:  signature,
	}, nonce)
	if err == nil {
		t.Fatal("expected expired timestamp error")
	}
}
