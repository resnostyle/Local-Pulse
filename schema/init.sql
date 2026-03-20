-- All timestamps are stored in UTC.
CREATE TABLE IF NOT EXISTS events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  start_time DATETIME NOT NULL,
  end_time DATETIME,
  venue VARCHAR(255),
  city VARCHAR(100),
  category VARCHAR(100),
  source VARCHAR(255),
  source_url VARCHAR(1000),
  recurring TINYINT(1) DEFAULT 0,
  fingerprint VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT chk_end_after_start CHECK (end_time IS NULL OR end_time >= start_time),
  INDEX idx_start_time (start_time),
  INDEX idx_city (city),
  INDEX idx_category (category)
);

CREATE TABLE IF NOT EXISTS sources (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL UNIQUE,
  source_type VARCHAR(50) NOT NULL,
  url VARCHAR(1000),
  config JSON,
  schedule_interval_minutes INT NOT NULL DEFAULT 360,
  retry_count INT NOT NULL DEFAULT 0,
  max_retries INT NOT NULL DEFAULT 5,
  backoff_until DATETIME,
  enabled TINYINT(1) DEFAULT 1,
  etag VARCHAR(255),
  last_modified VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_id INT NOT NULL,
  status ENUM('success','error','skipped','no_change') NOT NULL,
  events_found INT DEFAULT 0,
  events_inserted INT DEFAULT 0,
  duration_ms INT,
  error_message TEXT,
  http_status INT,
  started_at DATETIME NOT NULL,
  finished_at DATETIME,
  FOREIGN KEY (source_id) REFERENCES sources(id),
  INDEX idx_source_status (source_id, status),
  INDEX idx_source_started (source_id, started_at),
  INDEX idx_started (started_at)
);
