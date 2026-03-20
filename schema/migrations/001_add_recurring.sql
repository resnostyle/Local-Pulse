-- Add recurring column for events that repeat (e.g. weekly meetings).
-- Guarded: only runs if column does not already exist (safe for re-runs).
SET @col_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'events'
    AND column_name = 'recurring'
);

SET @sql = IF(@col_exists = 0,
  'ALTER TABLE events ADD COLUMN recurring TINYINT(1) DEFAULT 0 AFTER source_url',
  'SELECT 1'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
