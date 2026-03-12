-- Run this in Supabase SQL Editor to add price breakdown columns

-- Add new price columns
ALTER TABLE lots ADD COLUMN IF NOT EXISTS hammer_price DECIMAL(10, 2);
ALTER TABLE lots ADD COLUMN IF NOT EXISTS price_with_premium DECIMAL(10, 2);
ALTER TABLE lots ADD COLUMN IF NOT EXISTS price_total DECIMAL(10, 2);

-- Migrate existing data: sold_price becomes hammer_price
UPDATE lots SET hammer_price = sold_price WHERE hammer_price IS NULL;

-- Calculate price_with_premium (hammer + 21% buyer's premium)
UPDATE lots SET price_with_premium = ROUND(hammer_price * 1.21, 2);

-- Calculate price_total (with VAT for applicable items, otherwise same as premium)
UPDATE lots SET price_total = CASE 
    WHEN vat_applicable = TRUE THEN ROUND(price_with_premium * 1.20, 2)
    ELSE price_with_premium
END;

-- Verify the update
SELECT 
    lot_number,
    item_name,
    hammer_price,
    price_with_premium,
    price_total,
    vat_applicable
FROM lots 
LIMIT 10;
