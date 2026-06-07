-- Campus secondhand platform MySQL initialization script.
-- Run after backing up the CloudBase MySQL database.
-- This script is non-destructive: it only creates missing tables and indexes.

CREATE TABLE IF NOT EXISTS cloud_documents (
  collection_name VARCHAR(64) NOT NULL,
  document_id CHAR(24) NOT NULL,
  doc LONGTEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (collection_name, document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id CHAR(24) NOT NULL PRIMARY KEY,
  openid VARCHAR(128) NULL UNIQUE,
  phone VARCHAR(32) NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL DEFAULT '',
  nickname VARCHAR(64) NOT NULL DEFAULT '',
  avatar_url VARCHAR(512) NOT NULL DEFAULT '',
  profile_completed TINYINT(1) NOT NULL DEFAULT 0,
  identity_type VARCHAR(32) NOT NULL DEFAULT '',
  last_login_at DATETIME NULL,
  campus VARCHAR(64) NOT NULL DEFAULT '',
  student_no VARCHAR(64) NOT NULL DEFAULT '',
  verified_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
  credit_score INT NOT NULL DEFAULT 100,
  roles JSON NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_status (status),
  INDEX idx_users_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS categories (
  id CHAR(24) NOT NULL PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(64) NOT NULL,
  parent_id CHAR(24) NULL,
  sort_order INT NOT NULL DEFAULT 0,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_categories_parent (parent_id),
  INDEX idx_categories_enabled_sort (enabled, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
  id CHAR(24) NOT NULL PRIMARY KEY,
  seller_id CHAR(24) NOT NULL,
  category_id CHAR(24) NOT NULL,
  title VARCHAR(120) NOT NULL,
  description TEXT NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  original_price DECIMAL(10,2) NULL,
  item_condition VARCHAR(32) NOT NULL DEFAULT '',
  stock INT NOT NULL DEFAULT 1,
  campus VARCHAR(64) NOT NULL DEFAULT '',
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  view_count INT NOT NULL DEFAULT 0,
  favorite_count INT NOT NULL DEFAULT 0,
  sold_count INT NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_products_seller (seller_id),
  INDEX idx_products_category_status (category_id, status),
  INDEX idx_products_status_created (status, created_at),
  INDEX idx_products_price (price),
  CONSTRAINT fk_products_seller FOREIGN KEY (seller_id) REFERENCES users(id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS product_images (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id CHAR(24) NOT NULL,
  image_url VARCHAR(1024) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_product_images_product (product_id),
  CONSTRAINT fk_product_images_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS favorites (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id CHAR(24) NOT NULL,
  product_id CHAR(24) NOT NULL,
  favorited_price DECIMAL(10,2) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_favorites_user_product (user_id, product_id),
  INDEX idx_favorites_product (product_id),
  CONSTRAINT fk_favorites_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_favorites_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
  id CHAR(24) NOT NULL PRIMARY KEY,
  order_no VARCHAR(64) NOT NULL UNIQUE,
  buyer_id CHAR(24) NOT NULL,
  seller_id CHAR(24) NOT NULL,
  product_id CHAR(24) NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  pay_amount DECIMAL(10,2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending_payment',
  payment_mode VARCHAR(32) NOT NULL DEFAULT 'mock',
  paid_at DATETIME NULL,
  shipped_at DATETIME NULL,
  completed_at DATETIME NULL,
  cancelled_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_orders_buyer_status (buyer_id, status),
  INDEX idx_orders_seller_status (seller_id, status),
  INDEX idx_orders_product (product_id),
  CONSTRAINT fk_orders_buyer FOREIGN KEY (buyer_id) REFERENCES users(id),
  CONSTRAINT fk_orders_seller FOREIGN KEY (seller_id) REFERENCES users(id),
  CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversations (
  id VARCHAR(128) NOT NULL PRIMARY KEY,
  product_id CHAR(24) NULL,
  buyer_id CHAR(24) NOT NULL,
  seller_id CHAR(24) NOT NULL,
  last_message_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_conversations_buyer (buyer_id),
  INDEX idx_conversations_seller (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
  id CHAR(24) NOT NULL PRIMARY KEY,
  conversation_id VARCHAR(128) NOT NULL,
  sender_id CHAR(24) NOT NULL,
  receiver_id CHAR(24) NOT NULL,
  message_type VARCHAR(32) NOT NULL DEFAULT 'text',
  content TEXT NOT NULL,
  read_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_messages_conversation_created (conversation_id, created_at),
  INDEX idx_messages_receiver_read (receiver_id, read_at),
  CONSTRAINT fk_messages_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id),
  CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ai_generation_logs (
  id CHAR(24) NOT NULL PRIMARY KEY,
  user_id CHAR(24) NOT NULL,
  feature_type VARCHAR(32) NOT NULL,
  model VARCHAR(64) NOT NULL,
  input_summary VARCHAR(512) NOT NULL DEFAULT '',
  output_summary VARCHAR(512) NOT NULL DEFAULT '',
  success TINYINT(1) NOT NULL DEFAULT 0,
  error_message VARCHAR(1024) NOT NULL DEFAULT '',
  latency_ms INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ai_logs_user_created (user_id, created_at),
  INDEX idx_ai_logs_feature_created (feature_type, created_at),
  CONSTRAINT fk_ai_logs_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admin_logs (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  actor_id CHAR(24) NOT NULL,
  action VARCHAR(64) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(64) NOT NULL,
  result VARCHAR(32) NOT NULL DEFAULT '',
  detail TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_admin_logs_actor_created (actor_id, created_at),
  INDEX idx_admin_logs_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS appeals (
  id CHAR(24) NOT NULL PRIMARY KEY,
  order_id CHAR(24) NOT NULL,
  applicant_id CHAR(24) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  reason TEXT NOT NULL,
  result TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_appeals_order (order_id),
  INDEX idx_appeals_status_created (status, created_at),
  CONSTRAINT fk_appeals_order FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_appeals_applicant FOREIGN KEY (applicant_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stats_snapshots (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  metric_name VARCHAR(64) NOT NULL,
  metric_value DECIMAL(14,2) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_stats_snapshot (snapshot_date, metric_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
