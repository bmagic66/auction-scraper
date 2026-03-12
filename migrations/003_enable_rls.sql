-- Run this in Supabase SQL Editor to enable Row Level Security

-- Enable RLS on tables
ALTER TABLE auctions ENABLE ROW LEVEL SECURITY;
ALTER TABLE lots ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any (to avoid conflicts)
DROP POLICY IF EXISTS "Public read access for auctions" ON auctions;
DROP POLICY IF EXISTS "Public read access for lots" ON lots;
DROP POLICY IF EXISTS "Service role full access auctions" ON auctions;
DROP POLICY IF EXISTS "Service role full access lots" ON lots;

-- Public read access (anyone with anon key can SELECT)
CREATE POLICY "Public read access for auctions" ON auctions 
    FOR SELECT USING (true);

CREATE POLICY "Public read access for lots" ON lots 
    FOR SELECT USING (true);

-- Service role full access (scraper uses service_role key for INSERT/UPDATE)
CREATE POLICY "Service role full access auctions" ON auctions 
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access lots" ON lots 
    FOR ALL USING (auth.role() = 'service_role');

-- Verify policies
SELECT tablename, policyname, permissive, roles, cmd 
FROM pg_policies 
WHERE schemaname = 'public';
