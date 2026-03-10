package handlers

import (
	"database/sql"
	"html/template"
	"net/http"
	"strings"

	"local-pulse/go/db"
	"local-pulse/go/models"
)

// APIHandler holds shared dependencies for HTTP handlers.
type APIHandler struct {
	DB   *sql.DB
	Tmpl *template.Template
}

// eventsPageData holds data for the events page.
type eventsPageData struct {
	Events       []models.Event
	ActiveFilter string
}

// Index handles GET /
func (h *APIHandler) Index(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	events, err := db.ListEvents(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	data := eventsPageData{Events: events, ActiveFilter: "all"}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := h.Tmpl.ExecuteTemplate(w, "base.html", data); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

// EventsHTML handles GET /events
func (h *APIHandler) EventsHTML(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEvents(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "all")
}

// EventsTodayHTML handles GET /events/today
func (h *APIHandler) EventsTodayHTML(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEventsToday(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "today")
}

// EventsWeekendHTML handles GET /events/weekend
func (h *APIHandler) EventsWeekendHTML(w http.ResponseWriter, r *http.Request) {
	events, err := db.ListEventsWeekend(h.DB)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "weekend")
}

// EventsByCategoryHTML handles GET /events/category/:category
func (h *APIHandler) EventsByCategoryHTML(w http.ResponseWriter, r *http.Request) {
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
	h.renderEvents(w, r, events, category)
}

// renderEvents renders full page or fragment based on HX-Request header.
func (h *APIHandler) renderEvents(w http.ResponseWriter, r *http.Request, events []models.Event, activeFilter string) {
	data := eventsPageData{Events: events, ActiveFilter: activeFilter}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")

	if r.Header.Get("HX-Request") != "" {
		if err := h.Tmpl.ExecuteTemplate(w, "events_section_inner", data); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
		}
		return
	}

	if err := h.Tmpl.ExecuteTemplate(w, "base.html", data); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}
