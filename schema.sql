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

-- Sample data — safe to re-run any number of times, will not duplicate
INSERT INTO tickets (title, status, priority, category, created_by)
SELECT * FROM (VALUES
    ('Cannot log into dashboard', 'open', 'high', 'account', 'alice@example.com'),
    ('Export button not working', 'in_progress', 'medium', 'bug', 'bob@example.com'),
    ('Feature request: dark mode', 'resolved', 'low', 'feature_request', 'carol@example.com')
) AS seed(title, status, priority, category, created_by)
WHERE NOT EXISTS (
    SELECT 1 FROM tickets t WHERE t.title = seed.title
);

INSERT INTO ticket_messages (ticket_id, message_text, author)
SELECT t.ticket_id, seed.message_text, seed.author
FROM (VALUES
    ('Cannot log into dashboard', 'I keep getting an invalid password error even after resetting.', 'alice@example.com'),
    ('Cannot log into dashboard', 'Thanks for reporting — can you confirm which browser you are using?', 'support@example.com'),
    ('Export button not working', 'The export to CSV button does nothing when clicked.', 'bob@example.com'),
    ('Export button not working', 'We can reproduce this on Firefox, investigating now.', 'support@example.com'),
    ('Feature request: dark mode', 'Would love a dark mode option for late-night use.', 'carol@example.com'),
    ('Feature request: dark mode', 'Dark mode has been added in the latest release. Closing this out!', 'support@example.com')
) AS seed(ticket_title, message_text, author)
JOIN tickets t ON t.title = seed.ticket_title
WHERE NOT EXISTS (
    SELECT 1 FROM ticket_messages m
    WHERE m.ticket_id = t.ticket_id AND m.message_text = seed.message_text
);

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
