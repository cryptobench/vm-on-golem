package discovery

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"github.com/gorilla/websocket"
)

type Server struct {
	config   Config
	registry *Registry
	upgrader websocket.Upgrader
}

func NewServer(config Config) *Server {
	return &Server{
		config:   config,
		registry: NewRegistry(),
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool { return true },
		},
	}
}

func (s *Server) ListenAndServe() error {
	log.Printf("Starting central discovery service on %s", s.config.Address())
	return http.ListenAndServe(s.config.Address(), s.Handler())
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", s.health)
	mux.HandleFunc(apiV1Prefix+"/discovery/providers", s.providerDiscoverySocket)
	mux.HandleFunc(apiV1Prefix+"/discovery/requestors", s.requestorDiscoverySocket)
	return newRateLimitMiddleware(mux, s.config.RateLimitPerMinute)
}

func (s *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "healthy"})
}

func (s *Server) providerDiscoverySocket(w http.ResponseWriter, r *http.Request) {
	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("provider websocket upgrade failed: %v", err)
		return
	}
	defer conn.Close()

	nonce := randomNonce()
	providerID := ""
	if err := conn.WriteJSON(newEvent("hello", event{
		"protocol": protocolName,
		"nonce":    nonce,
	})); err != nil {
		return
	}

	defer func() {
		if providerID != "" {
			s.registry.RemoveProvider(providerID)
		}
	}()

	raw, err := readJSONMessage(conn)
	if err != nil {
		return
	}
	var authMessage providerAuthenticateMessage
	if err := json.Unmarshal(raw, &authMessage); err != nil || authMessage.Type != "authenticate" {
		sendWebsocketError(conn, "invalid provider authenticate message", websocket.CloseUnsupportedData)
		return
	}
	providerID, err = verifyProviderAuth(authMessage, nonce)
	if err != nil {
		sendWebsocketError(conn, err.Error(), websocket.ClosePolicyViolation)
		return
	}
	if err := conn.WriteJSON(newEvent("authenticated", event{"provider_id": providerID})); err != nil {
		return
	}
	log.Printf("Provider discovery websocket authenticated provider_id=%s", providerID)

	for {
		raw, err := readJSONMessage(conn)
		if err != nil {
			if !isNormalClose(err) {
				log.Printf("provider websocket read failed provider_id=%s error=%v", providerID, err)
			}
			return
		}
		messageType, err := decodeMessageType(raw)
		if err != nil {
			sendWebsocketError(conn, err.Error(), websocket.CloseUnsupportedData)
			return
		}
		switch messageType {
		case "advertisement.upsert":
			var message providerUpsertMessage
			if err := json.Unmarshal(raw, &message); err != nil {
				sendWebsocketError(conn, err.Error(), websocket.CloseUnsupportedData)
				return
			}
			if err := message.Advertisement.Validate(); err != nil {
				sendWebsocketError(conn, err.Error(), websocket.CloseUnsupportedData)
				return
			}
			advertisement := s.registry.UpsertProvider(providerID, message.Advertisement)
			if err := conn.WriteJSON(newEvent("advertisement.accepted", event{
				"advertisement": advertisement,
			})); err != nil {
				return
			}
		case "advertisement.remove":
			s.registry.RemoveProvider(providerID)
			if err := conn.WriteJSON(newEvent("advertisement.removed", event{
				"provider_id": providerID,
			})); err != nil {
				return
			}
		default:
			sendWebsocketError(conn, "unsupported provider message type: "+messageType, websocket.CloseUnsupportedData)
			return
		}
	}
}

func (s *Server) requestorDiscoverySocket(w http.ResponseWriter, r *http.Request) {
	conn, err := s.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("requestor websocket upgrade failed: %v", err)
		return
	}
	defer conn.Close()
	defer s.registry.DisconnectRequestor(conn)

	if err := conn.WriteJSON(newEvent("hello", event{"protocol": protocolName})); err != nil {
		return
	}

	for {
		raw, err := readJSONMessage(conn)
		if err != nil {
			if !isNormalClose(err) {
				log.Printf("requestor websocket read failed: %v", err)
			}
			return
		}
		var message requestorSubscribeMessage
		if err := json.Unmarshal(raw, &message); err != nil || message.Type != "subscribe" {
			sendWebsocketError(conn, "invalid requestor subscribe message", websocket.CloseUnsupportedData)
			return
		}
		if err := message.Filters.Validate(); err != nil {
			sendWebsocketError(conn, err.Error(), websocket.CloseUnsupportedData)
			return
		}
		advertisements := s.registry.Subscribe(conn, message.Filters)
		if err := s.registry.WriteSnapshot(conn, advertisements); err != nil {
			return
		}
	}
}

func readJSONMessage(conn *websocket.Conn) ([]byte, error) {
	messageType, raw, err := conn.ReadMessage()
	if err != nil {
		return nil, err
	}
	if messageType != websocket.TextMessage {
		return nil, errors.New("websocket message must be text")
	}
	return raw, nil
}

func sendWebsocketError(conn *websocket.Conn, message string, closeCode int) {
	_ = conn.WriteJSON(map[string]string{"type": "error", "error": message})
	_ = conn.WriteControl(
		websocket.CloseMessage,
		websocket.FormatCloseMessage(closeCode, message),
		utcNow().Add(websocketCloseDeadline),
	)
}

func isNormalClose(err error) bool {
	return websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway, websocket.CloseNoStatusReceived)
}

func writeJSON(w http.ResponseWriter, status int, value interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
