package db

import (
	"database/sql"
	"time"

	"local-pulse/go/models"
)

// ListEvents returns all events ordered by start_time.
func ListEvents(db *sql.DB) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events ORDER BY start_time ASC")
}

// ListEventsToday returns events starting today (UTC).
func ListEventsToday(db *sql.DB) ([]models.Event, error) {
	start := time.Now().UTC().Truncate(24 * time.Hour)
	end := start.Add(24 * time.Hour)
	return listEventsByRange(db, start, end)
}

// ListEventsWeekend returns events from Saturday 00:00 through Sunday 23:59 (UTC).
func ListEventsWeekend(db *sql.DB) ([]models.Event, error) {
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
	sunday := saturday.Add(48 * time.Hour)
	return listEventsByRange(db, saturday, sunday)
}

// ListEventsByCategory returns events in the given category.
func ListEventsByCategory(db *sql.DB, category string) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE category = ? ORDER BY start_time ASC", category)
}

func listEventsByRange(db *sql.DB, start, end time.Time) ([]models.Event, error) {
	return listEventsByQuery(db, "SELECT id, title, description, start_time, end_time, venue, city, category, source, source_url, fingerprint, created_at, updated_at FROM events WHERE start_time >= ? AND start_time < ? ORDER BY start_time ASC", start, end)
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
