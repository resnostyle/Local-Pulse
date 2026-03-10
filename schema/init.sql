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
  fingerprint VARCHAR(64) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_start_time (start_time),
  INDEX idx_city (city),
  INDEX idx_category (category)
);
