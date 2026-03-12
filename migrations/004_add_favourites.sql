-- Add is_favourited column to lots table
ALTER TABLE lots ADD COLUMN IF NOT EXISTS is_favourited BOOLEAN DEFAULT FALSE;

-- Add index for efficient filtering by favourite status
CREATE INDEX IF NOT EXISTS idx_lots_is_favourited ON lots(is_favourited);
