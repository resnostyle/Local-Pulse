package db

import (
	"database/sql"
	"math"
	"time"

	"local-pulse/go/models"
)

const DefaultPageSize = 20

// ListCategories returns distinct categories ordered alphabetically.
func ListCategories(db *sql.DB) ([]string, error) {
	rows, err := db.Query("SELECT DISTINCT category FROM events WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
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

// ListEvents returns all events ordered by start_time.
func ListEvents(db *sql.DB) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events ORDER BY start_time ASC")
}

// ListEventsPaginated returns events with limit/offset. Returns (events, totalCount, error).
func ListEventsPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
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

// ListEventsToday returns events starting today (UTC).
func ListEventsToday(db *sql.DB) ([]models.Event, error) {
	start, end := todayRange()
	return listEventsByRange(db, start, end)
}

// ListEventsTodayPaginated returns today's events with pagination.
func ListEventsTodayPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if page < 1 {
		page = 1
	}
	start, end := todayRange()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE start_time >= ? AND start_time < ?", start, end)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE start_time >= ? AND start_time < ? ORDER BY start_time ASC LIMIT ? OFFSET ?", start, end, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// ListEventsWeekend returns events from Saturday 00:00 through Sunday 23:59 (UTC).
func ListEventsWeekend(db *sql.DB) ([]models.Event, error) {
	saturday, sunday := weekendRange()
	return listEventsByRange(db, saturday, sunday)
}

// ListEventsWeekendPaginated returns weekend events with pagination.
func ListEventsWeekendPaginated(db *sql.DB, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if page < 1 {
		page = 1
	}
	saturday, sunday := weekendRange()
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE start_time >= ? AND start_time < ?", saturday, sunday)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE start_time >= ? AND start_time < ? ORDER BY start_time ASC LIMIT ? OFFSET ?", saturday, sunday, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

// ListEventsByCategory returns events in the given category.
func ListEventsByCategory(db *sql.DB, category string) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE category = ? ORDER BY start_time ASC", category)
}

// ListEventsByCategoryPaginated returns category events with pagination.
func ListEventsByCategoryPaginated(db *sql.DB, category string, page, pageSize int) ([]models.Event, int, error) {
	if pageSize <= 0 {
		pageSize = DefaultPageSize
	}
	if page < 1 {
		page = 1
	}
	total, err := countEvents(db, "SELECT COUNT(*) FROM events WHERE category = ?", category)
	if err != nil {
		return nil, 0, err
	}
	offset := (page - 1) * pageSize
	events, err := listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE category = ? ORDER BY start_time ASC LIMIT ? OFFSET ?", category, pageSize, offset)
	if err != nil {
		return nil, 0, err
	}
	return events, total, nil
}

func todayRange() (time.Time, time.Time) {
	start := time.Now().UTC().Truncate(24 * time.Hour)
	return start, start.Add(24 * time.Hour)
}

func weekendRange() (time.Time, time.Time) {
	now := time.Now().UTC()
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
