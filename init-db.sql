-- Initialize databases for Dendrite and Leaknote
-- This runs on first PostgreSQL startup
-- NOTE: Passwords are replaced by setup.sh

-- Create Dendrite database and user
CREATE USER dendrite WITH PASSWORD 'rH0_AZEt7ZV0SW2LE0Ab';
CREATE DATABASE dendrite OWNER dendrite;

-- Create Leaknote database and user
CREATE USER leaknote WITH PASSWORD 'gZ5_6V7NYhCbRj5gpGgB';
CREATE DATABASE leaknote OWNER leaknote;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dendrite TO dendrite;
GRANT ALL PRIVILEGES ON DATABASE leaknote TO leaknote;

-- Connect to leaknote database to create extensions
\c leaknote
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
