import os
import time
import re
import argparse
from playwright.sync_api import sync_playwright
from database import get_client

def parse_price(price_text):
    if not price_text:
        return None
    # Extract number after currency symbol
    match = re.search(r'[£$€]\s*([\d,]+(?:\.\d{2})?)', price_text)
    if match:
        return float(match.group(1).replace(',', ''))
    return None

def main():
    parser = argparse.ArgumentParser(description="Live Auction Scraper")
    parser.add_argument("url", help="Live auction URL")
    parser.add_argument("--auction-id", required=True, type=int, help="Auction ID in database")
    args = parser.parse_args()

    print(f"📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    print(f"🎥 Starting live scraper for Auction ID: {args.auction_id}")
    print(f"🔗 URL: {args.url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False to see it working/debug login
        page = browser.new_page()
        
        # Navigate
        print("🚀 Navigating to auction page...")
        page.goto(args.url, timeout=60000)
        
        # Wait for load - might need manual login if it redirects
        print("⏳ Waiting for auction interface...")
        try:
            page.wait_for_selector("a.lot-details-signpost", timeout=30000)
            print("✅ Auction interface loaded!")
        except:
            print("⚠️ Timeout waiting for selector. Please ensure you are logged in if required.")
            # Continue anyway in case it loads slowly
            
        while True:
            try:
                # 1. Get Current Lot
                # Selector: a.lot-details-signpost > span:last-child
                lot_elem = page.locator("a.lot-details-signpost > span:last-child").first
                if not lot_elem.is_visible():
                    print("⚠️ Current lot info not visible. Retrying in 30s...")
                    time.sleep(30)
                    continue
                
                current_lot = lot_elem.text_content().strip()
                
                # 2. Get Current Price
                # Find the container with "Current Price" text
                try:
                    price_label = page.get_by_text("Current Price", exact=False).first
                    if price_label.count() > 0:
                        # Use the container text for parsing
                        lot_details_text = price_label.locator("..").inner_text()
                    else:
                        lot_details_text = ""
                except Exception:
                    lot_details_text = ""
                
                # Look for "Current Price" followed by currency and number
                # Matches: "Current Price \n £ \n 40" or "Current Bid £40"
                price_match = re.search(r'(?:Current Price|Current Bid).*?[£$€]\s*([\d,]+(?:\.\d{2})?)', lot_details_text, re.DOTALL | re.IGNORECASE)
                
                price_text = None
                if price_match:
                    price_text = price_match.group(1)
                    current_price = float(price_text.replace(',', ''))
                else:
                    # Fallback: Just look for any currency number if "Current Price" text isn't strictly sequential
                    # This might be risky if there are other prices, but usually Current is prominent
                    fallback_match = re.search(r'[£$€]\s*([\d,]+(?:\.\d{2})?)', lot_details_text)
                    if fallback_match:
                         price_text = fallback_match.group(1)
                         current_price = float(price_text.replace(',', ''))
                    else:
                        current_price = None

                print(f"🔹 Live State: Lot {current_lot} | Parsed Price: {current_price} (from text block)")
                
                if current_lot and current_price is not None:
                    # 3. Update Database
                    # We update hammer_price.
                    print(f"💾 Updating DB: Lot {current_lot} -> £{current_price}")
                    
                    data = {
                        "hammer_price": current_price,
                        "status": "live" # Mark as live/active
                    }
                    
                    # Update lots table where auction_id and lot_number match
                    result = client.table("lots").update(data).match({
                        "auction_id": args.auction_id, 
                        "lot_number": current_lot
                    }).execute()
                    
                # 4. Batch Scrape Visible List (History & Upcoming)
                # The list area contains text like "Lot 123 Sold £50" or "Lot 124 Live"
                try:
                    list_area = page.locator("#lot-list-area")
                    if list_area.is_visible():
                        list_text = list_area.inner_text()
                        # Regex to find: Lot Number -> Status -> Price (optional)
                        # Pattern matches: "Lot 123... Sold... £50" or "Lot 123... Live"
                        # We use non-greedy matching to keep them separate
                        
                        # Regex explanation:
                        # Lot\s+(\S+)        : Matches "Lot" followed by number (e.g. "2201" or "2201A")
                        # .*?                : Random text in between (e.g. description)
                        # (Sold|Live|Passed) : Status
                        # .*?                : Text in between
                        # ([£$€]\s*[\d,]+)?  : Optional Price
                        
                        matches = re.finditer(r'Lot\s+([A-Za-z0-9]+).*?(Sold|Live|Passed).*?([£$€]\s*[\d,]+)?', list_text, re.DOTALL | re.IGNORECASE)
                        
                        updates_count = 0
                        for m in matches:
                            l_num = m.group(1)
                            status_raw = m.group(2).lower()
                            price_raw = m.group(3)
                            
                            status = "pending"
                            if "sold" in status_raw:
                                status = "sold"
                            elif "live" in status_raw:
                                status = "live"
                            elif "passed" in status_raw:
                                status = "passed"
                                
                            hammer_price = parse_price(price_raw) if price_raw else None
                            
                            # Update DB
                            # We only update if we have meaningful info (Sold/Passed, or Live)
                            data = {"status": status}
                            if hammer_price is not None:
                                data["hammer_price"] = hammer_price
                            
                            client.table("lots").update(data).match({
                                "auction_id": args.auction_id,
                                "lot_number": l_num
                            }).execute()
                            updates_count += 1
                        
                        if updates_count > 0:
                            print(f"📦 Batch updated {updates_count} lots from list history.")
                            
                except Exception as e:
                    print(f"⚠️ Error in batch scrape: {e}")

            except Exception as e:
                print(f"❌ Error in poll loop: {e}")
            
            print("💤 Sleeping for 30 seconds...")
            time.sleep(30)
            
            # Refresh to keep session alive and ensure fresh DOM
            try:
                print("🔄 Refreshing page...")
                page.reload()
                page.wait_for_selector("a.lot-details-signpost", timeout=30000)
            except Exception as e:
                 print(f"⚠️ Refresh failed: {e}")

        browser.close()

if __name__ == "__main__":
    main()
