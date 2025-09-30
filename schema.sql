-- Database & user (hapus kalau sudah dibuat terpisah)
-- CREATE DATABASE IF NOT EXISTS kapster_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- CREATE USER IF NOT EXISTS 'absen_user'@'localhost' IDENTIFIED BY 'absen_pass';
-- GRANT ALL PRIVILEGES ON kapster_db.* TO 'absen_user'@'localhost';
-- FLUSH PRIVILEGES;

USE kapster_db;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  username VARCHAR(80) NOT NULL UNIQUE,
  email VARCHAR(120) NOT NULL UNIQUE,
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
  customer_email VARCHAR(120) NULL,     -- email pelanggan (optional)
  payment_type VARCHAR(20) NOT NULL,    -- cash/qris/ewallet/transfer
  total INT NOT NULL,
  discount INT NULL DEFAULT 0,
  cash_given INT NULL,
  change_amount INT NULL,
  created_at DATETIME NOT NULL,

  -- invoice per-hari
  invoice_seq INT NULL,                 -- urutan per hari: 1,2,3...
  invoice_code VARCHAR(50) NULL,        -- format: INV-DD/MM/YYYY-###
  discount_name VARCHAR(120) DEFAULT NULL,

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

-- =========================
-- CUSTOMERS
-- =========================
CREATE TABLE IF NOT EXISTS customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  phone VARCHAR(30) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT uq_customers_phone UNIQUE (phone)
) ENGINE=InnoDB;

-- Tambah kolom pada TRANSACTIONS untuk relasi & freeze angka kunjungan
ALTER TABLE transactions
  ADD COLUMN customer_id INT NULL,
  ADD COLUMN visit_number INT NULL,
  ADD CONSTRAINT fk_tx_customer FOREIGN KEY (customer_id) REFERENCES customers(id);

-- DISCOUNT RULES
CREATE TABLE IF NOT EXISTS discount_rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  discount_type VARCHAR(10) NOT NULL, -- 'nominal' atau 'persen'
  value INT NOT NULL, -- nominal (Rp) atau persen (1-100)
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
) ENGINE=InnoDB;


-- SEED layanan (aman karena UNIQUE name)
INSERT INTO services (name, price, is_active) VALUES
('Potong Rambut', 35000, TRUE),
('Shaving', 15000, TRUE),
('Bleaching', 120000, TRUE)
ON DUPLICATE KEY UPDATE price=VALUES(price), is_active=VALUES(is_active);

-- SEED admin user
INSERT INTO users (name, username, email, password_hash, role, is_active_user)
VALUES ('Kenny', 'admin',
'kenny.putrajaya@gmail.com',
'pbkdf2:sha256:600000$6n6oFqfP$2f2e4b6b7c9eac4d0fcab3f2f9bc6d1c9d5c0b3c0be78f0a0b4b8f1f4d6e2c1a',
'admin', TRUE);
