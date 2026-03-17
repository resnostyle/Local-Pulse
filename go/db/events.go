package db

import (
	"database/sql"
	"math"
	"time"

	"local-pulse/go/models"
)

const DefaultPageSize = 20

// NowFunc returns the current time; override in tests for deterministic behavior.
var NowFunc = func() time.Time { return time.Now().UTC() }
const MaxPageSize = 100

// startOfToday returns midnight UTC of the current day; used to filter out past dates.
func startOfToday() time.Time {
	return NowFunc().Truncate(24 * time.Hour)
}

// visibleEventsWhere returns the WHERE clause for events that are upcoming or ongoing (end_date in future).
const visibleEventsWhere = "(start_time >= ?) OR (end_time IS NOT NULL AND end_time >= ?)"

// ListCategories returns distinct categories for visible events (upcoming or ongoing).
func ListCategories(db *sql.DB) ([]string, error) {
	cutoff := startOfToday()
	rows, err := db.Query("SELECT DISTINCT category FROM events WHERE category IS NOT NULL AND category != '' AND ("+visibleEventsWhere+") ORDER BY category ASC", cutoff, cutoff)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var categories []string
	for rows.Next() {
		var c string
		if err := rows.Scan(&c); err != nil {
			return nil, err
		}
		categories = append(categories, c)
	}
	return categories, rows.Err()
}

// ListAllEventsPaginated returns ALL events (no date filter) with pagination. For admin use.
func ListAllEventsPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if pageSize > MaxPageSize {
		pageSize = MaxPageSize
	}
	if page < 1 {
		page = 1
	}
	total, err := countEvents(db, "SELECT COUNT(*) FROM events")
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events ORDER BY start_time ASC LIMIT ? OFFSET ?", pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// ListEvents returns visible events (upcoming or ongoing), ordered by start_time.
func ListEvents(db *sql.DB) ([]models.Event, error) {
	cutoff := startOfToday()
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+visibleEventsWhere+") ORDER BY start_time ASC", cutoff, cutoff)
}

// ListEventsPaginated returns visible events (upcoming or ongoing) with limit/offset. Returns (events, totalCount, error).
func ListEventsPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if pageSize > MaxPageSize {
		pageSize = MaxPageSize
	}
	if page < 1 {
		page = 1
	}
	cutoff := startOfToday()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE ("+visibleEventsWhere+")", cutoff, cutoff)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+visibleEventsWhere+") ORDER BY start_time ASC LIMIT ? OFFSET ?", cutoff, cutoff, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// overlapRangeWhere: events overlapping [rangeStart, rangeEnd).
// - end_time IS NULL: point-in-time check (start_time >= rangeStart)
// - end_time IS NOT NULL: range overlap (start_time < rangeEnd AND end_time > rangeStart)
// Params: rangeStart, rangeEnd, rangeStart
const overlapRangeWhere = "(end_time IS NULL AND start_time >= ?) OR (end_time IS NOT NULL AND start_time < ? AND end_time > ?)"

// ListEventsToday returns events happening today (starting today or ongoing through today).
func ListEventsToday(db *sql.DB) ([]models.Event, error) {
	start, end := todayRange()
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+overlapRangeWhere+") ORDER BY start_time ASC", start, end, start)
}

// ListEventsTodayPaginated returns today's events (including ongoing) with pagination.
func ListEventsTodayPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if pageSize > MaxPageSize {
		pageSize = MaxPageSize
	}
	if page < 1 {
		page = 1
	}
	start, end := todayRange()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE ("+overlapRangeWhere+")", start, end, start)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+overlapRangeWhere+") ORDER BY start_time ASC LIMIT ? OFFSET ?", start, end, start, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// ListEventsWeekend returns events happening this weekend (starting or ongoing).
func ListEventsWeekend(db *sql.DB) ([]models.Event, error) {
	saturday, sunday := weekendRange()
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+overlapRangeWhere+") ORDER BY start_time ASC", saturday, sunday, saturday)
}

// ListEventsWeekendPaginated returns weekend events (including ongoing) with pagination.
func ListEventsWeekendPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if pageSize > MaxPageSize {
		pageSize = MaxPageSize
	}
	if page < 1 {
		page = 1
	}
	saturday, sunday := weekendRange()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE ("+overlapRangeWhere+")", saturday, sunday, saturday)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE ("+overlapRangeWhere+") ORDER BY start_time ASC LIMIT ? OFFSET ?", saturday, sunday, saturday, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// ListEventsByCategory returns visible events (upcoming or ongoing) in the given category.
func ListEventsByCategory(db *sql.DB, category string) ([]models.Event, error) {
	cutoff := startOfToday()
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE category = ? AND ("+visibleEventsWhere+") ORDER BY start_time ASC", category, cutoff, cutoff)
}

// ListEventsByCategoryPaginated returns visible events (upcoming or ongoing) in category with pagination.
func ListEventsByCategoryPaginated(db *sql.DB, category string, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if pageSize > MaxPageSize {
		pageSize = MaxPageSize
	}
	if page < 1 {
		page = 1
	}
	cutoff := startOfToday()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE category = ? AND ("+visibleEventsWhere+")", category, cutoff, cutoff)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE category = ? AND ("+visibleEventsWhere+") ORDER BY start_time ASC LIMIT ? OFFSET ?", category, cutoff, cutoff, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

func todayRange() (time.Time, time.Time) {
	start := NowFunc().Truncate(24 * time.Hour)
	return start, start.Add(24 * time.Hour)
}

func weekendRange() (time.Time, time.Time) {
	now := NowFunc()
	weekday := now.Weekday()
	var saturday time.Time
	if weekday == time.Saturday {
		saturday = now.Truncate(24 * time.Hour)
	} else if weekday == time.Sunday {
		saturday = now.Add(-24 * time.Hour).Truncate(24 * time.Hour)
	} else {
		daysUntilSaturday := (int(time.Saturday) - int(weekday) + 7) % 7
		saturday = now.AddDate(0, 0, daysUntilSaturday).Truncate(24 * time.Hour)
	}
	return saturday, saturday.Add(48 * time.Hour)
}

func listEventsByRange(db *sql.DB, start, end time.Time) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE start_time >= ? AND start_time < ? ORDER BY start_time ASC", start, end)
}

func countEvents(db *sql.DB, query string, args ...any) (int, error) {
	var n int
	err := db.QueryRow(query, args...).Scan(&n)
	return n, err
}

// TotalPages returns the number of pages for a given total count and page size.
func TotalPages(totalCount, pageSize int) int {
	if pageSize <= 0 || totalCount <= 0 {
		return 1
	}
	return int(math.Ceil(float64(totalCount) / float64(pageSize)))
}

func listEventsByQuery(db *sql.DB, query string, args ...any) ([]models.Event, error) {
	rows, err := db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []models.Event
	for rows.Next() {
		var e models.Event
		err := rows.Scan(
			&e.ID,
			&e.Title,
			&e.Description,
			&e.StartTime,
			&e.EndTime,
			&e.Venue,
			&e.City,
			&e.Category,
			&e.Source,
			&e.SourceURL,
			&e.Fingerprint,
			&e.CreatedAt,
			&e.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		events = append(events, e)
	}
	return events, rows.Err()
}
