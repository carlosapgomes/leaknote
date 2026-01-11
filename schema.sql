-- Leaknote Database Schema
-- Run against the leaknote database

\c leaknote

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Dynamic Categories (LLM-inferred)
-- =============================================================================

CREATE TABLE people (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    context TEXT,
    follow_ups TEXT,
    last_touched TIMESTAMP WITH TIME ZONE,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'waiting', 'blocked', 'someday', 'done')),
    next_action TEXT,
    notes TEXT,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE ideas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    one_liner TEXT,
    elaboration TEXT,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE admin (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    due_date DATE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done')),
    notes TEXT,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Reference Categories (prefix required)
-- =============================================================================

CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    context TEXT,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE howtos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE snippets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- System Tables
-- =============================================================================

CREATE TABLE inbox_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_text TEXT NOT NULL,
    destination TEXT,
    record_id UUID,
    confidence REAL,
    status TEXT DEFAULT 'filed' CHECK (status IN ('filed', 'needs_review', 'fixed')),
    telegram_message_id TEXT NOT NULL,
    telegram_chat_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE pending_clarifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inbox_log_id UUID REFERENCES inbox_log(id) ON DELETE CASCADE,
    telegram_message_id TEXT NOT NULL,
    telegram_chat_id TEXT NOT NULL,
    suggested_category TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Full-text search indexes
CREATE INDEX idx_people_fts ON people USING gin(to_tsvector('english', name || ' ' || COALESCE(context, '') || ' ' || COALESCE(follow_ups, '')));
CREATE INDEX idx_projects_fts ON projects USING gin(to_tsvector('english', name || ' ' || COALESCE(next_action, '') || ' ' || COALESCE(notes, '')));
CREATE INDEX idx_ideas_fts ON ideas USING gin(to_tsvector('english', title || ' ' || COALESCE(one_liner, '') || ' ' || COALESCE(elaboration, '')));
CREATE INDEX idx_admin_fts ON admin USING gin(to_tsvector('english', name || ' ' || COALESCE(notes, '')));
CREATE INDEX idx_decisions_fts ON decisions USING gin(to_tsvector('english', title || ' ' || decision || ' ' || COALESCE(rationale, '')));
CREATE INDEX idx_howtos_fts ON howtos USING gin(to_tsvector('english', title || ' ' || content));
CREATE INDEX idx_snippets_fts ON snippets USING gin(to_tsvector('english', title || ' ' || content));

-- Status and date indexes
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_admin_status ON admin(status);
CREATE INDEX idx_admin_due_date ON admin(due_date);
CREATE INDEX idx_inbox_log_status ON inbox_log(status);
CREATE INDEX idx_inbox_log_telegram_message ON inbox_log(telegram_message_id);
CREATE INDEX idx_pending_telegram_message ON pending_clarifications(telegram_message_id);

-- =============================================================================
-- Permissions
-- =============================================================================
-- Grant permissions to leaknote user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO leaknote;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO leaknote;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO leaknote;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO leaknote;
