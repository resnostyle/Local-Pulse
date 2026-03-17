package models

import "time"

type Event struct {
	ID          int
	Title       string
	Description *string
	StartTime   time.Time
	EndTime     *time.Time
	Venue       *string
	City        *string
	Category    *string
	Source      *string
	SourceURL   *string
	Recurring   bool
	Fingerprint *string
	CreatedAt   time.Time
	UpdatedAt   time.Time
}
