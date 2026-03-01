-- Add first_name, last_name, email_verified to existing users table (MySQL)
-- Run if you already have users table without these columns
-- Run each statement; ignore "Duplicate column name" if column already exists

ALTER TABLE users ADD COLUMN first_name VARCHAR(100) NULL;
ALTER TABLE users ADD COLUMN last_name VARCHAR(100) NULL;
ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 1;

-- After adding, optionally set defaults for existing rows:
-- UPDATE users SET first_name = 'User', last_name = '' WHERE first_name IS NULL;
