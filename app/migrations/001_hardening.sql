-- Idempotent. Applied automatically at application start (see sewasetu/db.py).

-- Wrong-OTP attempt counter, so a 6-digit OTP cannot be brute-forced.
ALTER TABLE otps ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;

-- One application per mobile number, enforced by the database (the earlier
-- check-then-insert in the code could be raced). The seed data has no duplicates.
CREATE UNIQUE INDEX IF NOT EXISTS applications_mobile_uq ON applications (mobile);
CREATE UNIQUE INDEX IF NOT EXISTS applications_no_uq ON applications (application_no);

-- Status/admin/deemed-approval queries filtered 100,000 rows with no index.
CREATE INDEX IF NOT EXISTS applications_status_submitted_idx ON applications (status, submitted_at);
CREATE INDEX IF NOT EXISTS otps_mobile_id_idx ON otps (mobile, id DESC)
