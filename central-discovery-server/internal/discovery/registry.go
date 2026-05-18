package discovery

import (
	"strings"
	"sync"

	"github.com/gorilla/websocket"
)

type requestorConnection struct {
	mu                 sync.Mutex
	conn               *websocket.Conn
	filters            ResourceRequirements
	visibleProviderIDs map[string]bool
}

type Registry struct {
	mu             sync.Mutex
	advertisements map[string]Advertisement
	requestors     map[*websocket.Conn]*requestorConnection
}

func NewRegistry() *Registry {
	return &Registry{
		advertisements: make(map[string]Advertisement),
		requestors:     make(map[*websocket.Conn]*requestorConnection),
	}
}

func (r *Registry) UpsertProvider(providerID string, payload AdvertisementPayload) Advertisement {
	r.mu.Lock()
	existing, exists := r.advertisements[providerID]
	now := utcNow()
	advertisement := Advertisement{
		AdvertisementPayload: payload,
		ProviderID:           providerID,
		CreatedAt:            now,
		UpdatedAt:            now,
	}
	if exists {
		advertisement.CreatedAt = existing.CreatedAt
	}
	r.advertisements[providerID] = advertisement
	requestors := r.requestorSnapshot()
	r.mu.Unlock()

	broadcastUpsert(advertisement, requestors)
	return advertisement
}

func (r *Registry) RemoveProvider(providerID string) bool {
	r.mu.Lock()
	_, exists := r.advertisements[providerID]
	if exists {
		delete(r.advertisements, providerID)
	}
	requestors := r.requestorSnapshot()
	r.mu.Unlock()

	if !exists {
		return false
	}
	broadcastRemove(providerID, requestors)
	return true
}

func (r *Registry) Subscribe(conn *websocket.Conn, filters ResourceRequirements) []Advertisement {
	r.mu.Lock()
	defer r.mu.Unlock()

	requestor := r.requestors[conn]
	if requestor == nil {
		requestor = &requestorConnection{
			conn:               conn,
			visibleProviderIDs: make(map[string]bool),
		}
		r.requestors[conn] = requestor
	}
	requestor.mu.Lock()
	defer requestor.mu.Unlock()
	requestor.filters = filters
	requestor.visibleProviderIDs = make(map[string]bool)

	matching := make([]Advertisement, 0)
	for _, advertisement := range r.advertisements {
		if MatchesFilters(advertisement, filters) {
			matching = append(matching, advertisement)
			requestor.visibleProviderIDs[advertisement.ProviderID] = true
		}
	}
	return matching
}

func (r *Registry) DisconnectRequestor(conn *websocket.Conn) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.requestors, conn)
}

func (r *Registry) WriteSnapshot(conn *websocket.Conn, advertisements []Advertisement) error {
	r.mu.Lock()
	requestor := r.requestors[conn]
	r.mu.Unlock()
	if requestor == nil {
		return conn.WriteJSON(newEvent("snapshot", event{"advertisements": advertisements}))
	}
	requestor.mu.Lock()
	defer requestor.mu.Unlock()
	return conn.WriteJSON(newEvent("snapshot", event{"advertisements": advertisements}))
}

func (r *Registry) Snapshot(filters ResourceRequirements) []Advertisement {
	r.mu.Lock()
	defer r.mu.Unlock()
	matching := make([]Advertisement, 0)
	for _, advertisement := range r.advertisements {
		if MatchesFilters(advertisement, filters) {
			matching = append(matching, advertisement)
		}
	}
	return matching
}

func MatchesFilters(advertisement Advertisement, filters ResourceRequirements) bool {
	resources := advertisement.Resources
	if filters.CPU != nil && resources["cpu"] < *filters.CPU {
		return false
	}
	if filters.Memory != nil && resources["memory"] < *filters.Memory {
		return false
	}
	if filters.Storage != nil && resources["storage"] < *filters.Storage {
		return false
	}
	if filters.Country != nil && !strings.EqualFold(advertisement.Country, *filters.Country) {
		return false
	}
	if filters.Platform != nil {
		if advertisement.Platform == nil || *advertisement.Platform != *filters.Platform {
			return false
		}
	}
	return true
}

func (r *Registry) requestorSnapshot() []*requestorConnection {
	requestors := make([]*requestorConnection, 0, len(r.requestors))
	for _, requestor := range r.requestors {
		requestors = append(requestors, requestor)
	}
	return requestors
}

func broadcastUpsert(advertisement Advertisement, requestors []*requestorConnection) {
	for _, requestor := range requestors {
		requestor.mu.Lock()
		matches := MatchesFilters(advertisement, requestor.filters)
		wasVisible := requestor.visibleProviderIDs[advertisement.ProviderID]
		if matches {
			requestor.visibleProviderIDs[advertisement.ProviderID] = true
			_ = requestor.conn.WriteJSON(newEvent("provider.upsert", event{
				"advertisement": advertisement,
			}))
		} else if wasVisible {
			delete(requestor.visibleProviderIDs, advertisement.ProviderID)
			_ = requestor.conn.WriteJSON(newEvent("provider.remove", event{
				"provider_id": advertisement.ProviderID,
			}))
		}
		requestor.mu.Unlock()
	}
}

func broadcastRemove(providerID string, requestors []*requestorConnection) {
	for _, requestor := range requestors {
		requestor.mu.Lock()
		if !requestor.visibleProviderIDs[providerID] {
			requestor.mu.Unlock()
			continue
		}
		delete(requestor.visibleProviderIDs, providerID)
		_ = requestor.conn.WriteJSON(newEvent("provider.remove", event{
			"provider_id": providerID,
		}))
		requestor.mu.Unlock()
	}
}
