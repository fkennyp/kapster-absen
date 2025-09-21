-- Database & user (hapus kalau sudah dibuat terpisah)
-- CREATE DATABASE IF NOT EXISTS absen_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- CREATE USER IF NOT EXISTS 'absen_user'@'localhost' IDENTIFIED BY 'absen_pass';
-- GRANT ALL PRIVILEGES ON absen_db.* TO 'absen_user'@'localhost';
-- FLUSH PRIVILEGES;

USE absen_db;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'kapster',
  is_active_user BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

-- ATTENDANCE
CREATE TABLE IF NOT EXISTS attendance (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  date DATE NOT NULL,
  check_in DATETIME NULL,
  check_out DATETIME NULL,
  notes VARCHAR(255) NULL,
  CONSTRAINT fk_att_user FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX idx_att_date (date)
) ENGINE=InnoDB;

-- SERVICES
CREATE TABLE IF NOT EXISTS services (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  price INT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT uq_services_name UNIQUE (name)
) ENGINE=InnoDB;

-- TRANSACTIONS (header)
CREATE TABLE IF NOT EXISTS transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,                 -- kapster yang membuat transaksi
  barber_name VARCHAR(120) NULL,        -- nama barbershop (optional)
  customer_name VARCHAR(120) NULL,      -- nama pelanggan (wajib by app validation)
  payment_type VARCHAR(20) NOT NULL,    -- cash/qris/ewallet/transfer
  total INT NOT NULL,
  cash_given INT NULL,
  change_amount INT NULL,
  created_at DATETIME NOT NULL,

  -- invoice per-hari
  invoice_seq INT NULL,                 -- urutan per hari: 1,2,3...
  invoice_code VARCHAR(50) NULL,        -- format: INV-DD/MM/YYYY-###

  FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX idx_tx_created_at (created_at),
  INDEX idx_tx_invoice_seq (invoice_seq)
) ENGINE=InnoDB;

-- TRANSACTION ITEMS (detail)
CREATE TABLE IF NOT EXISTS transaction_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  transaction_id INT NOT NULL,
  service_id INT NOT NULL,
  qty INT NOT NULL DEFAULT 1,
  price_each INT NOT NULL,
  line_total INT NOT NULL,
  FOREIGN KEY (transaction_id) REFERENCES transactions(id),
  FOREIGN KEY (service_id) REFERENCES services(id)
) ENGINE=InnoDB;

-- SEED layanan (aman karena UNIQUE name)
INSERT INTO services (name, price, is_active) VALUES
('Potong Rambut', 35000, TRUE),
('Shaving', 15000, TRUE),
('Bleaching', 120000, TRUE)
ON DUPLICATE KEY UPDATE price=VALUES(price), is_active=VALUES(is_active);
