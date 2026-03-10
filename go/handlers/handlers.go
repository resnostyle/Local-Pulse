package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	"local-pulse/go/db"
)

// APIHandler holds shared dependencies for HTTP handlers.
type APIHandler struct {
	DB *sql.DB
}

// Events handles GET /events
func (h *APIHandler) Events(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEvents(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(events)
}

// EventsToday handles GET /events/today
func (h *APIHandler) EventsToday(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEventsToday(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(events)
}

// EventsWeekend handles GET /events/weekend
func (h *APIHandler) EventsWeekend(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEventsWeekend(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(events)
}

// EventsByCategory handles GET /events/category/:category
func (h *APIHandler) EventsByCategory(w http.ResponseWriter, r *http.Request) {
	category := strings.TrimPrefix(r.URL.Path, "/events/category/")
	category = strings.Trim(category, "/")
	if category == "" {
		http.Error(w, "category is required", http.StatusBadRequest)
		return
	}
	events, err := db.ListEventsByCategory(h.DB, category)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(events)
}
