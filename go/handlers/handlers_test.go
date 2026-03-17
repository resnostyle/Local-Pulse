package handlers

import (
	"encoding/json"
	"errors"
	"html/template"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
)

func TestHealth_Returns200WhenDBHealthy(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	mock.ExpectPing()

	tmpl := template.Must(template.New("").Parse(""))
	h := &APIHandler{DB: db, Tmpl: tmpl}

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h.Health(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("Health: status = %d, want 200", rec.Code)
	}
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("Health: invalid JSON: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("Health: status = %q, want ok", body["status"])
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestHealth_Returns503WhenDBUnhealthy(t *testing.T) {
	db, mock, err := sqlmock.New(sqlmock.MonitorPingsOption(true))
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	mock.ExpectPing().WillReturnError(errors.New("connection refused"))

	tmpl := template.Must(template.New("").Parse(""))
	h := &APIHandler{DB: db, Tmpl: tmpl}

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()

	h.Health(rec, req)

	if rec.Code != http.StatusServiceUnavailable {
		t.Errorf("Health: status = %d, want 503", rec.Code)
	}
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatalf("Health: invalid JSON: %v", err)
	}
	if body["status"] != "unhealthy" {
		t.Errorf("Health: status = %q, want unhealthy", body["status"])
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestParsePage(t *testing.T) {
	tests := []struct {
		name string
		url  string
		want int
	}{
		{"no page param", "/events", 1},
		{"page 1", "/events?page=1", 1},
		{"page 2", "/events?page=2", 2},
		{"page 10", "/events?page=10", 10},
		{"invalid page", "/events?page=abc", 1},
		{"zero page", "/events?page=0", 1},
		{"negative page", "/events?page=-1", 1},
		{"empty page", "/events?page=", 1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			r := httptest.NewRequest(http.MethodGet, "http://test"+tt.url, nil)
			if got := parsePage(r); got != tt.want {
				t.Errorf("parsePage() = %d, want %d", got, tt.want)
			}
		})
	}
}

func newTestHandler(t *testing.T) (*APIHandler, sqlmock.Sqlmock) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}

	funcMap := template.FuncMap{
		"pathEscape": func(s string) string {
			return url.PathEscape(s)
		},
		"formatDateTime": func(t time.Time) string {
			return t.Format("Mon Jan 2, 2006 at 3:04 PM")
		},
		"pageURL": func(filterPath string, page int) string {
			if page <= 1 {
				return filterPath
			}
			return filterPath + "?page=" + strconv.Itoa(page)
		},
		"add": func(a, b int) int { return a + b },
		"sub": func(a, b int) int { return a - b },
		"mul": func(a, b int) int { return a * b },
		"seq": func(start, end int) []int {
			if start > end {
				return nil
			}
			s := make([]int, end-start+1)
			for i := range s {
				s[i] = start + i
			}
			return s
		},
	}
	tmpl := template.Must(template.New("").Funcs(funcMap).ParseGlob("../templates/*.html"))

	return &APIHandler{DB: db, Tmpl: tmpl}, mock
}

func TestIndex_Returns200(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(5)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WillReturnRows(eventRows)

	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WillReturnRows(rows)

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()

	h.Index(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("Index: status = %d, want 200", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestIndex_NotFoundForNonRoot(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	req := httptest.NewRequest(http.MethodGet, "/foo", nil)
	rec := httptest.NewRecorder()

	h.Index(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("Index: status = %d, want 404", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unfulfilled expectations: %v", err)
	}
}

func TestEventsHTML_Returns200(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(0)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WillReturnRows(eventRows)

	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WillReturnRows(rows)

	req := httptest.NewRequest(http.MethodGet, "/events", nil)
	rec := httptest.NewRecorder()

	h.EventsHTML(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("EventsHTML: status = %d, want 200", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestEventsHTML_HTMXReturnsFragment(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(0)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WillReturnRows(eventRows)

	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WillReturnRows(rows)

	req := httptest.NewRequest(http.MethodGet, "/events", nil)
	req.Header.Set("HX-Request", "true")
	rec := httptest.NewRecorder()

	h.EventsHTML(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("EventsHTML: status = %d, want 200", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestEventsByCategoryHTML_EmptyCategoryReturns400(t *testing.T) {
	h, _ := newTestHandler(t)
	defer h.DB.Close()

	req := httptest.NewRequest(http.MethodGet, "/events/category/", nil)
	rec := httptest.NewRecorder()

	h.EventsByCategoryHTML(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Errorf("EventsByCategoryHTML: status = %d, want 400", rec.Code)
	}
}

func TestEventsByCategoryHTML_ValidCategory(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(3)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events WHERE category = \\?").
		WithArgs("Music").
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs("Music", 20, 0).
		WillReturnRows(eventRows)

	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WillReturnRows(rows)

	req := httptest.NewRequest(http.MethodGet, "/events/category/Music", nil)
	rec := httptest.NewRecorder()

	h.EventsByCategoryHTML(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("EventsByCategoryHTML: status = %d, want 200", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestEventsHTML_HTMXWithPageParam(t *testing.T) {
	h, mock := newTestHandler(t)
	defer h.DB.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(50)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(20, 20).
		WillReturnRows(eventRows)

	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WillReturnRows(rows)

	req := httptest.NewRequest(http.MethodGet, "/events?page=2", nil)
	req.Header.Set("HX-Request", "true")
	rec := httptest.NewRecorder()

	h.EventsHTML(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("EventsHTML: status = %d, want 200", rec.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}
