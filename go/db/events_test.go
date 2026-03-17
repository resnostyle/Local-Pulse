package db

import (
	"database/sql"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
)

func TestTotalPages(t *testing.T) {
	tests := []struct {
		name       string
		totalCount int
		pageSize   int
		want       int
	}{
		{"zero total returns 1", 0, 20, 1},
		{"zero pageSize returns 1", 25, 0, 1},
		{"negative total returns 1", -1, 20, 1},
		{"negative pageSize returns 1", 25, -5, 1},
		{"exact fit", 20, 20, 1},
		{"one extra", 21, 20, 2},
		{"multiple pages", 100, 20, 5},
		{"partial last page", 55, 20, 3},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := TotalPages(tt.totalCount, tt.pageSize); got != tt.want {
				t.Errorf("TotalPages(%d, %d) = %d, want %d", tt.totalCount, tt.pageSize, got, tt.want)
			}
		})
	}
}

func TestListCategories(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()
	cutoff := fixedNow.Truncate(24 * time.Hour) // startOfToday in tests

	rows := sqlmock.NewRows([]string{"category"}).
		AddRow("Arts").
		AddRow("Music").
		AddRow("Sports")
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WithArgs(cutoff, cutoff).
		WillReturnRows(rows)

	got, err := ListCategories(db)
	if err != nil {
		t.Errorf("ListCategories: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	want := []string{"Arts", "Music", "Sports"}
	if len(got) != len(want) {
		t.Errorf("ListCategories: got %d categories, want %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("ListCategories[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

func TestListCategories_Empty(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	cutoff := fixedNow.Truncate(24 * time.Hour)
	rows := sqlmock.NewRows([]string{"category"})
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WithArgs(cutoff, cutoff).
		WillReturnRows(rows)

	got, err := ListCategories(db)
	if err != nil {
		t.Errorf("ListCategories: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("ListCategories: got %d categories, want 0", len(got))
	}
}

func TestListEventsPaginated(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	cutoff := fixedNow.Truncate(24 * time.Hour)
	// Count query
	countRows := sqlmock.NewRows([]string{"count"}).AddRow(45)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WithArgs(cutoff, cutoff).
		WillReturnRows(countRows)

	// List query
	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"}).
		AddRow(1, "Test Event", "Desc", fixedNow, fixedNow.Add(time.Hour), "Venue A", "Raleigh", "Music", "Source", "https://example.com", "fp1", fixedNow, fixedNow)
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(cutoff, cutoff, 20, 0).
		WillReturnRows(eventRows)

	events, total, err := ListEventsPaginated(db, 1, 20)
	if err != nil {
		t.Errorf("ListEventsPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if total != 45 {
		t.Errorf("total = %d, want 45", total)
	}
	if len(events) != 1 {
		t.Errorf("len(events) = %d, want 1", len(events))
	}
	if events[0].Title != "Test Event" {
		t.Errorf("events[0].Title = %q, want %q", events[0].Title, "Test Event")
	}
}

func TestListEventsPaginated_InvalidPageUsesDefault(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	cutoff := fixedNow.Truncate(24 * time.Hour)
	countRows := sqlmock.NewRows([]string{"count"}).AddRow(0)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WithArgs(cutoff, cutoff).
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"})
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(cutoff, cutoff, DefaultPageSize, 0).
		WillReturnRows(eventRows)

	_, _, err = ListEventsPaginated(db, 0, 0)
	if err != nil {
		t.Errorf("ListEventsPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestListCategories_QueryError(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	cutoff := fixedNow.Truncate(24 * time.Hour)
	mock.ExpectQuery("SELECT DISTINCT category FROM events").
		WithArgs(cutoff, cutoff).
		WillReturnError(sql.ErrConnDone)

	_, err = ListCategories(db)
	if err == nil {
		t.Error("ListCategories: expected error, got nil")
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
}

func TestListEventsByCategoryPaginated(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	cutoff := fixedNow.Truncate(24 * time.Hour)
	countRows := sqlmock.NewRows([]string{"count"}).AddRow(10)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events WHERE category = \\?").
		WithArgs("Music", cutoff, cutoff).
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"}).
		AddRow(1, "Concert", nil, fixedNow, nil, "Arena", "Cary", "Music", "Visit Raleigh", "https://example.com", "fp1", fixedNow, fixedNow)
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs("Music", cutoff, cutoff, 20, 0).
		WillReturnRows(eventRows)

	events, total, err := ListEventsByCategoryPaginated(db, "Music", 1, 20)
	if err != nil {
		t.Errorf("ListEventsByCategoryPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if total != 10 {
		t.Errorf("total = %d, want 10", total)
	}
	if len(events) != 1 {
		t.Errorf("len(events) = %d, want 1", len(events))
	}
	if events[0].Category == nil || *events[0].Category != "Music" {
		t.Errorf("events[0].Category = %v, want Music", events[0].Category)
	}
}

func TestListEventsTodayPaginated(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	start := fixedNow.Truncate(24 * time.Hour)
	end := start.Add(24 * time.Hour)

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(2)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events WHERE \\(\\(end_time IS NULL AND start_time >= \\?\\) OR \\(end_time IS NOT NULL AND start_time < \\? AND end_time > \\?\\)\\)").
		WithArgs(start, end, start).
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"}).
		AddRow(1, "Today Event", nil, fixedNow, nil, "Venue", "Raleigh", "Music", "Source", "https://example.com", "fp1", fixedNow, fixedNow)
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(start, end, start, 20, 0).
		WillReturnRows(eventRows)

	events, total, err := ListEventsTodayPaginated(db, 1, 20)
	if err != nil {
		t.Errorf("ListEventsTodayPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if total != 2 {
		t.Errorf("total = %d, want 2", total)
	}
	if len(events) != 1 {
		t.Errorf("len(events) = %d, want 1", len(events))
	}
	if events[0].Title != "Today Event" {
		t.Errorf("events[0].Title = %q, want %q", events[0].Title, "Today Event")
	}
}

func TestListEventsWeekendPaginated(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC) // Monday
	NowFunc = func() time.Time { return fixedNow }
	defer func() { NowFunc = func() time.Time { return time.Now().UTC() } }()

	saturday := time.Date(2026, 3, 21, 0, 0, 0, 0, time.UTC)
	sunday := saturday.Add(48 * time.Hour)

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(1)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events WHERE \\(\\(end_time IS NULL AND start_time >= \\?\\) OR \\(end_time IS NOT NULL AND start_time < \\? AND end_time > \\?\\)\\)").
		WithArgs(saturday, sunday, saturday).
		WillReturnRows(countRows)

	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"}).
		AddRow(1, "Weekend Event", nil, saturday.Add(2*time.Hour), nil, "Park", "Cary", "Sports", "Source", "https://example.com", "fp1", fixedNow, fixedNow)
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(saturday, sunday, saturday, 20, 0).
		WillReturnRows(eventRows)

	events, total, err := ListEventsWeekendPaginated(db, 1, 20)
	if err != nil {
		t.Errorf("ListEventsWeekendPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if total != 1 {
		t.Errorf("total = %d, want 1", total)
	}
	if len(events) != 1 {
		t.Errorf("len(events) = %d, want 1", len(events))
	}
	if events[0].Title != "Weekend Event" {
		t.Errorf("events[0].Title = %q, want %q", events[0].Title, "Weekend Event")
	}
}

func TestListAllEventsPaginated(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New: %v", err)
	}
	defer db.Close()

	countRows := sqlmock.NewRows([]string{"count"}).AddRow(100)
	mock.ExpectQuery("SELECT COUNT\\(\\*\\) FROM events").
		WillReturnRows(countRows)

	fixedNow := time.Date(2026, 3, 16, 12, 0, 0, 0, time.UTC)
	eventRows := sqlmock.NewRows([]string{"id", "title", "description", "start_time", "end_time", "venue", "city", "category", "source", "source_url", "fingerprint", "created_at", "updated_at"}).
		AddRow(1, "Admin Event", "Past event", fixedNow.Add(-24*time.Hour), nil, "Old Venue", "Raleigh", "Arts", "Source", "https://example.com", "fp1", fixedNow, fixedNow)
	mock.ExpectQuery("SELECT id, title, description, start_time").
		WithArgs(50, 0).
		WillReturnRows(eventRows)

	events, total, err := ListAllEventsPaginated(db, 1, 50)
	if err != nil {
		t.Errorf("ListAllEventsPaginated: %v", err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("unfulfilled expectations: %v", err)
	}
	if total != 100 {
		t.Errorf("total = %d, want 100", total)
	}
	if len(events) != 1 {
		t.Errorf("len(events) = %d, want 1", len(events))
	}
	if events[0].Title != "Admin Event" {
		t.Errorf("events[0].Title = %q, want %q", events[0].Title, "Admin Event")
	}
}
