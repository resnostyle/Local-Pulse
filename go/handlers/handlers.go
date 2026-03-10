package handlers

import (
	"net/http"
)

// Events handles GET /events
func Events(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("events"))
}

// EventsToday handles GET /events/today
func EventsToday(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("events/today"))
}

// EventsWeekend handles GET /events/weekend
func EventsWeekend(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("events/weekend"))
}

// EventsByCategory handles GET /events/category/:category
func EventsByCategory(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("events/category"))
}
