-- ============================================================
-- Support Ticketing System — Lakebase schema
-- ============================================================

-- Tables
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    priority    TEXT NOT NULL DEFAULT 'medium',
    category    TEXT,
    created_by  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    message_id    SERIAL PRIMARY KEY,
    ticket_id     INTEGER NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    message_text  TEXT NOT NULL,
    author        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);

-- Sample data (already loaded if you ran this in Step 2 — safe to skip)
INSERT INTO tickets (title, status, priority, category, created_by) VALUES
('Cannot log into dashboard', 'open', 'high', 'account', 'alice@example.com'),
('Export button not working', 'in_progress', 'medium', 'bug', 'bob@example.com'),
('Feature request: dark mode', 'resolved', 'low', 'feature_request', 'carol@example.com')
ON CONFLICT DO NOTHING;

INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES
(1, 'I keep getting an invalid password error even after resetting.', 'alice@example.com'),
(1, 'Thanks for reporting — can you confirm which browser you are using?', 'support@example.com'),
(2, 'The export to CSV button does nothing when clicked.', 'bob@example.com'),
(2, 'We can reproduce this on Firefox, investigating now.', 'support@example.com'),
(3, 'Would love a dark mode option for late-night use.', 'carol@example.com'),
(3, 'Dark mode has been added in the latest release. Closing this out!', 'support@example.com')
ON CONFLICT DO NOTHING;

-- ============================================================
-- Run this AFTER you create the Databricks App (Step 4).
-- Replace <DATABRICKS_CLIENT_ID> with the value from your
-- app's "Environment" tab.
-- ============================================================

-- Enables the app's service principal to authenticate with OAuth tokens
CREATE EXTENSION IF NOT EXISTS databricks_auth;

SELECT databricks_create_role('<DATABRICKS_CLIENT_ID>', 'service_principal');

GRANT CONNECT ON DATABASE databricks_postgres TO "<DATABRICKS_CLIENT_ID>";
GRANT USAGE ON SCHEMA public TO "<DATABRICKS_CLIENT_ID>";
GRANT SELECT, INSERT, UPDATE, DELETE ON tickets, ticket_messages TO "<DATABRICKS_CLIENT_ID>";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "<DATABRICKS_CLIENT_ID>";
