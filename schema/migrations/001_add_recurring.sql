-- Add recurring column for events that repeat (e.g. weekly meetings).
-- Run this if your events table was created before this migration.
ALTER TABLE events ADD COLUMN recurring TINYINT(1) DEFAULT 0 AFTER source_url;
