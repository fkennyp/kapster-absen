-- Create database and user (run as MySQL root or admin)
CREATE DATABASE IF NOT EXISTS absen_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'absen_user'@'localhost'
    IDENTIFIED BY 'absen_pass';

GRANT ALL PRIVILEGES ON absen_db.* TO 'absen_user'@'localhost';

FLUSH PRIVILEGES;

-- Tables
USE absen_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'kapster',
    is_active_user BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS attendance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    date DATE NOT NULL,
    check_in DATETIME NULL,
    check_out DATETIME NULL,
    notes VARCHAR(255) NULL,
    CONSTRAINT fk_att_user FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_att_date (date)
);

-- Optional seed admin (replace password hash if needed)
-- You can also run: `flask bootstrap-admin`