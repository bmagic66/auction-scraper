-- Run this in Supabase SQL Editor to add the VAT column to existing database

-- Add vat_applicable column if it doesn't exist
ALTER TABLE lots ADD COLUMN IF NOT EXISTS vat_applicable BOOLEAN DEFAULT FALSE;

-- Update existing rows based on item_name containing +VAT
UPDATE lots 
SET vat_applicable = TRUE 
WHERE LOWER(item_name) LIKE '%+vat%' 
   OR LOWER(item_name) LIKE '%+ vat%';

-- Check results
SELECT 
    COUNT(*) AS total_lots,
    COUNT(*) FILTER (WHERE vat_applicable = TRUE) AS vat_lots,
    COUNT(*) FILTER (WHERE vat_applicable = FALSE) AS non_vat_lots
FROM lots;
