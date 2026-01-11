#!/bin/bash
# Initialize database for Leaknote
# This runs on first PostgreSQL startup
# Password is read from environment variable

set -e

# Default value (fallback)
LEAKNOTE_PW="${LEAKNOTE_DB_PASSWORD:-leaknote}"

echo "Initializing database..."

# Create Leaknote database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER leaknote WITH PASSWORD '${LEAKNOTE_PW}';
    CREATE DATABASE leaknote OWNER leaknote;
    GRANT ALL PRIVILEGES ON DATABASE leaknote TO leaknote;
EOSQL

echo "✓ Leaknote database and user created"

# Connect to leaknote database to create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "leaknote" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOSQL

echo "✓ Extensions created"

echo "Database initialization complete!"
