-- Create tenants, users, and tenant_admins tables for MySQL
-- Run against MySQL 8+ database

-- Tenants table (MySQL uses VARCHAR for plan, not native ENUM)
CREATE TABLE IF NOT EXISTS tenants (
    id CHAR(36) PRIMARY KEY,
    slug VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL UNIQUE,
    primary_admin_email VARCHAR(255) NOT NULL,
    plan ENUM('starter', 'professional', 'enterprise') NOT NULL DEFAULT 'starter',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_tenants_slug (slug),
    INDEX idx_tenants_domain (domain)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    tenant_id CHAR(36) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_users_email (email),
    INDEX idx_users_tenant_id (tenant_id),
    CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tenant admins (junction table: many admins per tenant)
CREATE TABLE IF NOT EXISTS tenant_admins (
    tenant_id CHAR(36) NOT NULL,
    user_id INT NOT NULL,
    PRIMARY KEY (tenant_id, user_id),
    CONSTRAINT fk_tenant_admins_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_tenant_admins_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
