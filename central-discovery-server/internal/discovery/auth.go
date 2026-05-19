package discovery

import (
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/crypto"
)

const authTimestampTolerance = 5 * time.Minute

func providerAuthMessage(providerID string, nonce string, timestamp string) string {
	return fmt.Sprintf("central-discovery-auth:%s:%s:%s", providerID, nonce, timestamp)
}

func verifyProviderAuth(message providerAuthenticateMessage, expectedNonce string) (string, error) {
	if message.Nonce != expectedNonce {
		return "", errors.New("provider auth nonce mismatch")
	}

	timestamp, err := time.Parse(time.RFC3339Nano, message.Timestamp)
	if err != nil {
		return "", errors.New("provider auth timestamp invalid")
	}
	age := utcNow().Sub(timestamp)
	if age < 0 {
		age = -age
	}
	if age > authTimestampTolerance {
		return "", errors.New("provider auth timestamp expired")
	}

	recovered, err := recoverPersonalSignAddress(
		providerAuthMessage(message.ProviderID, message.Nonce, message.Timestamp),
		message.Signature,
	)
	if err != nil {
		return "", fmt.Errorf("provider auth signature invalid: %w", err)
	}
	if !strings.EqualFold(recovered, message.ProviderID) {
		return "", errors.New("provider auth signature mismatch")
	}
	return common.HexToAddress(recovered).Hex(), nil
}

func recoverPersonalSignAddress(text string, signatureHex string) (string, error) {
	signature, err := hex.DecodeString(strings.TrimPrefix(signatureHex, "0x"))
	if err != nil {
		return "", err
	}
	if len(signature) != 65 {
		return "", fmt.Errorf("signature must be 65 bytes")
	}
	if signature[64] >= 27 {
		signature[64] -= 27
	}
	if signature[64] > 1 {
		return "", fmt.Errorf("signature recovery id must be 0 or 1")
	}

	hash := personalSignHash(text)
	publicKey, err := crypto.SigToPub(hash, signature)
	if err != nil {
		return "", err
	}
	return crypto.PubkeyToAddress(*publicKey).Hex(), nil
}

func personalSignHash(text string) []byte {
	prefix := fmt.Sprintf("\x19Ethereum Signed Message:\n%d", len(text))
	return crypto.Keccak256([]byte(prefix + text))
}
