package handlers

import (
	"database/sql"
	"encoding/json"
	"html/template"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"local-pulse/go/db"
	"local-pulse/go/models"
)

func buildNextPageURL(filterPath string, page int, searchQuery string) string {
	params := url.Values{}
	if page > 1 {
		params.Set("page", strconv.Itoa(page))
	}
	if searchQuery != "" {
		params.Set("q", searchQuery)
	}
	params.Set("append", "1")
	return filterPath + "?" + params.Encode()
}

// APIHandler holds shared dependencies for HTTP handlers.
type APIHandler struct {
	DB   *sql.DB
	Tmpl *template.Template
}

// Health handles GET /health. Returns 200 if DB is reachable, 503 otherwise.
func (h *APIHandler) Health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if err := h.DB.Ping(); err != nil {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]string{"status": "unhealthy"})
		return
	}
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// NotFound serves the custom 404 page.
func (h *APIHandler) NotFound(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusNotFound)
	if err := h.Tmpl.ExecuteTemplate(w, "404", nil); err != nil {
		log.Printf("404 template: %v", err)
		w.Write([]byte("Page not found"))
	}
}

// InternalError serves the custom 500 page.
func (h *APIHandler) InternalError(w http.ResponseWriter, r *http.Request, err error) {
	if err != nil {
		log.Printf("Internal error: %v", err)
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	if tplErr := h.Tmpl.ExecuteTemplate(w, "500", nil); tplErr != nil {
		log.Printf("500 template: %v", tplErr)
		w.Write([]byte("Internal Server Error"))
	}
}

// eventsPageData holds data for the events page.
type eventsPageData struct {
	Events       []models.Event
	ActiveFilter string
	Categories   []string
	Page         int
	PageSize     int
	TotalCount   int
	TotalPages   int
	ShowingStart int
	ShowingEnd   int
	FilterPath   string
	PageType     string // "index" or "events"
	SearchQuery  string
	HasMore      bool
	NextPageURL  string
}

// Index handles GET /
func (h *APIHandler) Index(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		h.NotFound(w, r)
		return
	}
	page := parsePage(r)
	pageSize := 12
	events, total, err := db.ListEventsPaginated(h.DB, page, pageSize)
	if err != nil {
		h.InternalError(w, r, err)
		return
	}
	categories, _ := db.ListCategories(h.DB)
	totalPages := db.TotalPages(total, pageSize)
	hasMore := page < totalPages
	nextPageURL := ""
	if hasMore {
		nextPageURL = buildNextPageURL("/", page+1, "")
	}
	data := eventsPageData{
		Events:       events,
		ActiveFilter: "all",
		Categories:   categories,
		Page:         page,
		PageSize:     pageSize,
		TotalCount:   total,
		TotalPages:   totalPages,
		ShowingStart: min((page-1)*pageSize+1, total),
		ShowingEnd:   min(page*pageSize, total),
		FilterPath:   "/",
		PageType:     "index",
		HasMore:      hasMore,
		NextPageURL:  nextPageURL,
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if r.Header.Get("HX-Request") != "" {
		tmplName := "events_section_inner"
		if r.URL.Query().Get("append") == "1" {
			tmplName = "event_cards"
		}
		if err := h.Tmpl.ExecuteTemplate(w, tmplName, data); err != nil {
			h.InternalError(w, r, err)
		}
		return
	}
	if err := h.Tmpl.ExecuteTemplate(w, "base.html", data); err != nil {
		h.InternalError(w, r, err)
	}
}

// EventsHTML handles GET /events
func (h *APIHandler) EventsHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		h.InternalError(w, r, err)
		return
	}
	h.renderEvents(w, r, events, "all", "/events", page, db.DefaultPageSize, total)
}

// EventsTodayHTML handles GET /events/today
func (h *APIHandler) EventsTodayHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsTodayPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		h.InternalError(w, r, err)
		return
	}
	h.renderEvents(w, r, events, "today", "/events/today", page, db.DefaultPageSize, total)
}

// EventsWeekendHTML handles GET /events/weekend
func (h *APIHandler) EventsWeekendHTML(w http.ResponseWriter, r *http.Request) {
	page := parsePage(r)
	events, total, err := db.ListEventsWeekendPaginated(h.DB, page, db.DefaultPageSize)
	if err != nil {
		h.InternalError(w, r, err)
		return
	}
	h.renderEvents(w, r, events, "weekend", "/events/weekend", page, db.DefaultPageSize, total)
}

// AdminHTML handles GET /admin - shows all events (no date filter).
func (h *APIHandler) AdminHTML(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/admin" {
		h.NotFound(w, r)
		return
	}
	page := parsePage(r)
	pageSize := 50
	events, total, err := db.ListAllEventsPaginated(h.DB, page, pageSize)
	if err != nil {
		h.InternalError(w, r, err)
		return
	}
	data := adminPageData{
		Events:       events,
		Page:         page,
		PageSize:     pageSize,
		TotalCount:   total,
		TotalPages:   db.TotalPages(total, pageSize),
		ShowingStart: min((page-1)*pageSize+1, total),
		ShowingEnd:   min(page*pageSize, total),
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := h.Tmpl.ExecuteTemplate(w, "admin.html", data); err != nil {
		h.InternalError(w, r, err)
	}
}

// adminPageData holds data for the admin page.
type adminPageData struct {
	Events       []models.Event
	Page         int
	PageSize     int
	TotalCount   int
	TotalPages   int
	ShowingStart int
	ShowingEnd   int
}

// SearchEventsHTML handles GET /events/search?q=...
func (h *APIHandler) SearchEventsHTML(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	page := parsePage(r)

	var events []models.Event
	var total int
	var err error

	if query == "" {
		events, total, err = db.ListEventsPaginated(h.DB, page, db.DefaultPageSize)
	} else {
		events, total, err = db.SearchEventsPaginated(h.DB, query, page, db.DefaultPageSize)
	}
	if err != nil {
		h.InternalError(w, r, err)
		return
	}

	categories, _ := db.ListCategories(h.DB)
	totalPages := db.TotalPages(total, db.DefaultPageSize)
	hasMore := page < totalPages
	nextPageURL := ""
	if hasMore {
		nextPageURL = buildNextPageURL("/events/search", page+1, query)
	}
	data := eventsPageData{
		Events:       events,
		ActiveFilter: "all",
		Categories:   categories,
		Page:         page,
		PageSize:     db.DefaultPageSize,
		TotalCount:   total,
		TotalPages:   totalPages,
		ShowingStart: min((page-1)*db.DefaultPageSize+1, total),
		ShowingEnd:   min(page*db.DefaultPageSize, total),
		FilterPath:   "/events/search",
		PageType:     "events",
		SearchQuery:  query,
		HasMore:      hasMore,
		NextPageURL:  nextPageURL,
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if r.Header.Get("HX-Request") != "" {
		if err := h.Tmpl.ExecuteTemplate(w, "event_cards", data); err != nil {
			h.InternalError(w, r, err)
		}
		return
	}
	if err := h.Tmpl.ExecuteTemplate(w, "base.html", data); err != nil {
		h.InternalError(w, r, err)
	}
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
		h.InternalError(w, r, err)
		return
	}
	h.renderEvents(w, r, events, category, "/events/category/"+url.PathEscape(category), page, db.DefaultPageSize, total)
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
	searchQuery := r.URL.Query().Get("q")
	totalPages := db.TotalPages(totalCount, pageSize)
	hasMore := page < totalPages
	nextPageURL := ""
	if hasMore {
		nextPageURL = buildNextPageURL(filterPath, page+1, searchQuery)
	}
	data := eventsPageData{
		Events:       events,
		ActiveFilter: activeFilter,
		Categories:   categories,
		Page:         page,
		PageSize:     pageSize,
		TotalCount:   totalCount,
		TotalPages:   totalPages,
		ShowingStart: min((page-1)*pageSize+1, totalCount),
		ShowingEnd:   min(page*pageSize, totalCount),
		FilterPath:   filterPath,
		PageType:     "events",
		SearchQuery:  searchQuery,
		HasMore:      hasMore,
		NextPageURL:  nextPageURL,
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")

	if r.Header.Get("HX-Request") != "" {
		tmplName := "events_section_inner"
		if r.URL.Query().Get("append") == "1" {
			tmplName = "event_cards"
		}
		if err := h.Tmpl.ExecuteTemplate(w, tmplName, data); err != nil {
			h.InternalError(w, r, err)
		}
		return
	}

	if err := h.Tmpl.ExecuteTemplate(w, "base.html", data); err != nil {
		h.InternalError(w, r, err)
	}
}
