package discovery

import (
	"crypto/rand"
	"encoding/base64"
	"time"
)

const websocketCloseDeadline = time.Second

func randomNonce() string {
	bytes := make([]byte, 24)
	if _, err := rand.Read(bytes); err != nil {
		panic(err)
	}
	return base64.RawURLEncoding.EncodeToString(bytes)
}
