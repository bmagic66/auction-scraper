-- Allow public users (anon) to update lots (specifically for toggling favourites)
-- Note: Supabase doesn't support column-level permissions in RLS policies directly in a simple way 
-- without just allowing update on the row.
-- First, ensure anon has update privilege on the table.
GRANT UPDATE (is_favourited) ON lots TO anon;
GRANT UPDATE (is_favourited) ON lots TO authenticated;
GRANT UPDATE (is_favourited) ON lots TO service_role;

-- Add RLS Policy to allow UPDATE for anon role
-- This policy allows updating ANY row.
CREATE POLICY "Enable update for anon" ON "lots" 
AS PERMISSIVE FOR UPDATE 
TO anon 
USING (true) 
WITH CHECK (true);

-- Also add for public just in case the role mapping is standard
CREATE POLICY "Enable update for public" ON "lots" 
AS PERMISSIVE FOR UPDATE 
TO public 
USING (true) 
WITH CHECK (true);
