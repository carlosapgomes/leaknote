-- Migration from Matrix to Telegram
-- This script migrates inbox_log and pending_clarifications tables
-- from Matrix event/room IDs to Telegram message/chat IDs

BEGIN;

-- Backup existing data
CREATE TABLE inbox_log_backup AS SELECT * FROM inbox_log;
CREATE TABLE pending_clarifications_backup AS SELECT * FROM pending_clarifications;

-- Add new columns (allow NULL temporarily)
ALTER TABLE inbox_log
  ADD COLUMN IF NOT EXISTS telegram_message_id TEXT,
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

ALTER TABLE pending_clarifications
  ADD COLUMN IF NOT EXISTS telegram_message_id TEXT,
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

-- Drop old columns
ALTER TABLE inbox_log
  DROP COLUMN IF EXISTS matrix_event_id,
  DROP COLUMN IF EXISTS matrix_room_id;

ALTER TABLE pending_clarifications
  DROP COLUMN IF EXISTS matrix_event_id,
  DROP COLUMN IF EXISTS matrix_room_id;

-- Make new columns NOT NULL after adding them
-- Note: This will fail if there's existing data without these columns
-- In that case, you'll need to either:
-- 1. Clear the tables first, or
-- 2. Set default values before making NOT NULL
ALTER TABLE inbox_log
  ALTER COLUMN telegram_message_id SET NOT NULL,
  ALTER COLUMN telegram_chat_id SET NOT NULL;

ALTER TABLE pending_clarifications
  ALTER COLUMN telegram_message_id SET NOT NULL,
  ALTER COLUMN telegram_chat_id SET NOT NULL;

-- Update indexes
DROP INDEX IF EXISTS idx_inbox_log_event_id;
CREATE INDEX idx_inbox_log_telegram_message ON inbox_log(telegram_message_id);

DROP INDEX IF EXISTS idx_pending_event_id;
CREATE INDEX idx_pending_telegram_message ON pending_clarifications(telegram_message_id);

COMMIT;
