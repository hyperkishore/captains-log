-- Add user_email to devices table for multi-tenant filtering
ALTER TABLE devices ADD COLUMN IF NOT EXISTS user_email TEXT;
CREATE INDEX IF NOT EXISTS idx_devices_user_email ON devices(user_email);
