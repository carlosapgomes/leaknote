-- Initialize databases for Dendrite and Second Brain
-- This runs on first PostgreSQL startup

-- Create Dendrite database and user
CREATE USER dendrite WITH PASSWORD 'dendrite-password-change-me';
CREATE DATABASE dendrite OWNER dendrite;

-- Create Second Brain database and user  
CREATE USER secondbrain WITH PASSWORD 'secondbrain-password-change-me';
CREATE DATABASE secondbrain OWNER secondbrain;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE dendrite TO dendrite;
GRANT ALL PRIVILEGES ON DATABASE secondbrain TO secondbrain;

-- Connect to secondbrain database to create extensions
\c secondbrain
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
