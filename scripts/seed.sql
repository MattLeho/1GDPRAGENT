-- Clear existing data to avoid duplicates (optional, strictly speaking we might want to keep other data but meant for fresh seed)
-- TRUNCATE requests, messages, received_data CASCADE;

-- 1. eBay (Processing)
INSERT INTO requests (company_name, domain, status, progress, notes, created_at)
VALUES ('eBay', 'ebay.com', 'processing', 40, 'Date started 05/11/2025', NOW());

-- 2. Amazon (Scheduled)
INSERT INTO requests (company_name, domain, status, progress, notes, next_action_date, created_at)
VALUES ('Amazon', 'amazon.com', 'scheduled', 10, '3 months left', '2025-09-16 00:00:00+00', NOW());

-- 3. Google (Action Required)
INSERT INTO requests (company_name, domain, status, progress, notes, created_at)
VALUES ('Google', 'google.com', 'action_required', 80, 'Previous Receipt 06/08/23', NOW());
