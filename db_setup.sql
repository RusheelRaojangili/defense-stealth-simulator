CREATE DATABASE IF NOT EXISTS stealth_defense_db;
USE stealth_defense_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    asset VARCHAR(50) NOT NULL,
    coating VARCHAR(100) NOT NULL,
    base_score FLOAT NOT NULL,
    coated_score FLOAT NOT NULL,
    reduction_pct FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert a default demo user (username: admin, password: password123)
INSERT IGNORE INTO users (id, username, password) VALUES (1, 'admin', 'password123');