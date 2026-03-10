package handlers

import (
	"database/sql"
	"html/template"
	"net/http"
	"strconv"
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
	Categories   []string
	Page        int
	PageSize    int
	TotalCount  int
	TotalPages  int
	FilterPath  string
	PageType    string // "index" or "events"
}

// Index handles GET /
func (h *APIHandler) Index(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	// Index shows featured events (first page, limited)
	page := parsePage(r)
	pageSize := 12
	events, total, err := db.ListEventsPaginated(h.DB, page, pageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	categories, _ := db.ListCategories(h.DB)
	data := eventsPageData{
		Events:       events,
		ActiveFilter: "all",
		Categories:   categories,
		Page:         page,
		PageSize:     pageSize,
		TotalCount:   total,
		TotalPages:   db.TotalPages(total, pageSize),
		FilterPath:   "/",
		PageType:     "index",
	}
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

// EventsHTML handles GET /events
func (h *APIHandler) EventsHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "all", "/events", page, db.DefaultPageSize, total)
}

// EventsTodayHTML handles GET /events/today
func (h *APIHandler) EventsTodayHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsTodayPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "today", "/events/today", page, db.DefaultPageSize, total)
}

// EventsWeekendHTML handles GET /events/weekend
func (h *APIHandler) EventsWeekendHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsWeekendPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, "weekend", "/events/weekend", page, db.DefaultPageSize, total)
}

// EventsByCategoryHTML handles GET /events/category/:category
func (h *APIHandler) EventsByCategoryHTML(w http.ResponseWriter, r *http.Request) {
	category := strings.TrimPrefix(r.URL.Path, "/events/category/")
	category = strings.Trim(category, "/")
	if category == "" {
		http.Error(w, "category is required", http.StatusBadRequest)
		return
	}
	page := parsePage(r)
	events, total, err := db.ListEventsByCategoryPaginated(h.DB, category, page, db.DefaultPageSize)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	h.renderEvents(w, r, events, category, "/events/category/"+category, page, db.DefaultPageSize, total)
}

func parsePage(r *http.Request) int {
	if p := r.URL.Query().Get("page"); p != "" {
		if n, err := strconv.Atoi(p); err == nil && n >= 1 {
			return n
		}
	}
	return 1
}

// renderEvents renders full page or fragment based on HX-Request header.
func (h *APIHandler) renderEvents(w http.ResponseWriter, r *http.Request, events []models.Event, activeFilter, filterPath string, page, pageSize, totalCount int) {
	categories, _ := db.ListCategories(h.DB)
	data := eventsPageData{
		Events:       events,
		ActiveFilter: activeFilter,
		Categories:   categories,
		Page:         page,
		PageSize:     pageSize,
		TotalCount:   totalCount,
		TotalPages:   db.TotalPages(totalCount, pageSize),
		FilterPath:   filterPath,
		PageType:     "events",
	}
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
