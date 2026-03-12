# Auction Scraper

Scrapes auction data (images, item names, sold prices) from auction websites and stores them in Supabase.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Supabase:**
   - Create a project at [supabase.com](https://supabase.com)
   - Copy `.env.example` to `.env` and fill in your credentials
   - Run the SQL in `schema.sql` in the Supabase SQL Editor

3. **Create storage bucket:**
   - In Supabase Dashboard → Storage → Create bucket named `auction-images`
   - Set it to public for easy image access

## Usage

```bash
python main.py "https://auction-url-here"
```

## Querying Data

```sql
-- Get all lots from an auction
SELECT * FROM lots WHERE auction_id = 1;

-- Search by item name
SELECT * FROM lots WHERE item_name ILIKE '%iphone%';

-- Get total sales value
SELECT SUM(sold_price) FROM lots;
```
