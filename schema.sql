-- Run this in Supabase SQL Editor to create the database schema

-- Auctions table
CREATE TABLE IF NOT EXISTS auctions (
    id SERIAL PRIMARY KEY,
    auction_url TEXT NOT NULL UNIQUE,
    auction_name TEXT,
    scrape_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Lots table
CREATE TABLE IF NOT EXISTS lots (
    id SERIAL PRIMARY KEY,
    auction_id INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
    lot_number TEXT NOT NULL,
    item_name TEXT,
    hammer_price DECIMAL(10, 2),
    price_with_premium DECIMAL(10, 2),
    price_total DECIMAL(10, 2),
    currency TEXT DEFAULT 'GBP',
    vat_applicable BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(auction_id, lot_number)
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_lots_auction_id ON lots(auction_id);
CREATE INDEX IF NOT EXISTS idx_lots_item_name ON lots USING gin(to_tsvector('english', item_name));
CREATE INDEX IF NOT EXISTS idx_lots_sold_price ON lots(sold_price);

-- Enable Row Level Security
ALTER TABLE auctions ENABLE ROW LEVEL SECURITY;
ALTER TABLE lots ENABLE ROW LEVEL SECURITY;

-- Public read access (for frontend)
CREATE POLICY "Public read access for auctions" ON auctions FOR SELECT USING (true);
CREATE POLICY "Public read access for lots" ON lots FOR SELECT USING (true);

-- Authenticated write access (for scraper with service_role key)
CREATE POLICY "Service role full access auctions" ON auctions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access lots" ON lots FOR ALL USING (auth.role() = 'service_role');

-- =====================================================
-- CATALOGUE SCRAPER ADDITIONS (run as migration)
-- =====================================================

-- Add columns for pre-auction catalogue data
ALTER TABLE lots ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
ALTER TABLE lots ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE lots ADD COLUMN IF NOT EXISTS lot_url TEXT;
ALTER TABLE lots ADD COLUMN IF NOT EXISTS lot_guid TEXT;
ALTER TABLE lots ADD COLUMN IF NOT EXISTS catalogue_scraped_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE lots ADD COLUMN IF NOT EXISTS results_scraped_at TIMESTAMP WITH TIME ZONE;

-- Add catalogue_id to auctions for i-bidder matching
ALTER TABLE auctions ADD COLUMN IF NOT EXISTS catalogue_id TEXT;

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_lots_status ON lots(status);
CREATE INDEX IF NOT EXISTS idx_lots_lot_guid ON lots(lot_guid);
CREATE INDEX IF NOT EXISTS idx_auctions_catalogue_id ON auctions(catalogue_id);

