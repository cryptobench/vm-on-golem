package discovery

import (
	"encoding/json"
	"time"
)

type event map[string]interface{}

func newEvent(eventType string, payload event) event {
	result := event{
		"type":         eventType,
		"generated_at": utcTimestamp(),
	}
	for key, value := range payload {
		result[key] = value
	}
	return result
}

func marshalEvent(eventType string, payload event) ([]byte, error) {
	return json.Marshal(newEvent(eventType, payload))
}

func utcNow() time.Time {
	return time.Now().UTC()
}

func utcTimestamp() string {
	return utcNow().Format(time.RFC3339Nano)
}
