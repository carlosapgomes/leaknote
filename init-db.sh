#!/bin/bash
# Initialize databases for Dendrite and Leaknote
# This runs on first PostgreSQL startup
# Passwords are read from environment variables dynamically

set -e

# Default values (fallback)
LEAKNOTE_PW="${LEAKNOTE_DB_PASSWORD:-leaknote}"
DENDRITE_PW="${DENDRITE_DB_PASSWORD:-dendrite}"

echo "Initializing databases..."

# Create Dendrite database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER dendrite WITH PASSWORD '${DENDRITE_PW}';
    CREATE DATABASE dendrite OWNER dendrite;
    GRANT ALL PRIVILEGES ON DATABASE dendrite TO dendrite;
EOSQL

echo "✓ Dendrite database and user created"

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
