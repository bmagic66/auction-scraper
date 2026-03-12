#!/usr/bin/env python3
"""
Live Auction Sync Service
Run this script during the auction to keep prices in sync automatically.
It polls the auction page every 60 seconds and efficiently updates only new or changed results.
"""
import time
import re
import argparse
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
from database import get_client

# Configuration
cancellation_point = 0.175  # 21% Buyer's Premium (Matches main.py)
VAT_RATE = 1.20 # 20% VAT

def get_db_state(client, auction_id):
    """Fetch current state of lots from DB to minimize writes."""
    response = client.table("lots").select("lot_number, status, hammer_price, item_name, vat_applicable").eq("auction_id", auction_id).execute()
    return {lot["lot_number"]: lot for lot in response.data}

def scrape_live_prices(url):
    """Scrape the current prices and status from the live page."""
    updates = {}
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Go to URL
            print(f"   Browsing {url}...")
            page.goto(url, timeout=60000)
            
            # Wait for content
            try:
                page.wait_for_selector("a.lot-info", timeout=15000)
            except:
                pass # Proceed anyway, might be empty or slow

            # Handle infinite scroll / lazy loading
            # Try to scroll the specific container if found, else window
            try:
                list_area = page.locator("#lots-list-container")
                if not list_area.is_visible():
                     list_area = page.locator("#lot-list-area")
                
                if list_area.is_visible():
                    # Scroll a few times to ensure we get recent lots
                    # For a live auction, we might need to scroll deep if we want *everything*,
                    # but usually, we just need to ensure we see the "sold" ones.
                    # If the user wants "sync everything", we attempt to load all.
                    for _ in range(5):
                        list_area.evaluate("el => el.scrollTop = el.scrollHeight")
                        time.sleep(1)
            except:
                pass

            # Extract data
            elements = page.locator("a.lot-info").all()
            
            for el in elements:
                try:
                    # Extract Lot Number
                    lot_text = el.locator(".lot-description strong").first.inner_text().strip().replace('.', '')
                    # Cleanup "4001A" etc
                    if not lot_text.isdigit():
                         # Keep letters if they are part of the lot number format
                         # Assuming format "4001" or "4001A"
                         lot_text = re.sub(r'[^0-9A-Z]', '', lot_text)
                    
                    lot_num = lot_text
                    
                    # Extract Status
                    status_el = el.locator(".status").first
                    status = status_el.inner_text().strip().lower() if status_el.is_visible() else "pending"
                    
                    # Extract Price
                    price = None
                    hammer_el = el.locator(".lot-hammer").first
                    if hammer_el.is_visible():
                        price_text = hammer_el.inner_text().strip()
                        # Extract number
                        match = re.search(r'[\d,]+(?:\.\d{2})?', price_text)
                        if match:
                            price = float(match.group(0).replace(',', ''))
                    
                    if "sold" in status and price is not None:
                        updates[lot_num] = {
                            "status": "sold",
                            "price": price
                        }
                    elif "passed" in status: # Optional: handle passed lots
                         updates[lot_num] = {
                            "status": "passed",
                            "price": None
                        }
                        
                except Exception:
                    continue
                    
            browser.close()
            
        except Exception as e:
            print(f"⚠️ Scraping error: {e}")
            
    return updates

def sync_loop(auction_id, url, interval=5):
    """Main loop."""
    print(f"🚀 Starting Live Sync for Auction {auction_id}")
    print(f"   URL: {url}")
    print(f"   Interval: {interval} seconds")
    print("   Press Ctrl+C to stop.\n")
    
    client = get_client(use_secret=True)
    
    while True:
        try:
            start_time = datetime.now()
            print(f"[{start_time.strftime('%H:%M:%S')}] Checking for updates...")
            
            # 1. Get DB State
            db_lots = get_db_state(client, auction_id)
            print(f"   Database has {len(db_lots)} lots.")
            
            # 2. Scrape Live
            live_data = scrape_live_prices(url)
            print(f"   Found {len(live_data)} results on page.")
            
            # 3. Calculate Deltas
            to_update = []
            
            for lot_num, live_info in live_data.items():
                if lot_num not in db_lots:
                    continue # Skip unknown lots or add logic to insert new ones
                
                db_lot = db_lots[lot_num]
                
                # Check if update needed
                needs_update = False
                
                # Status mismatch?
                if db_lot["status"] != live_info["status"]:
                    needs_update = True
                    
                # Price mismatch? (Only if sold)
                if live_info["status"] == "sold":
                    current_price = db_lot.get("hammer_price")
                    # Handle None
                    if current_price is None or float(current_price) != live_info["price"]:
                        needs_update = True
                        
                if needs_update:
                    # prepare update payload
                    payload = {
                        "status": live_info["status"]
                    }
                    
                    if live_info["status"] == "sold":
                        hammer = live_info["price"]
                        
                        # VAT Check
                        vat_applicable = db_lot.get("vat_applicable", False)
                        if not vat_applicable and db_lot.get("item_name"):
                             name = db_lot["item_name"].lower()
                             if '+vat' in name or '+ vat' in name:
                                 vat_applicable = True
                        
                        price_wp = round(hammer * (1 + cancellation_point), 2)
                        price_tot = round(price_wp * VAT_RATE, 2) if vat_applicable else price_wp
                        
                        payload.update({
                            "hammer_price": hammer,
                            "price_with_premium": price_wp,
                            "price_total": price_tot
                        })
                    
                    to_update.append((lot_num, payload))
            
            # 4. Apply Updates
            if to_update:
                print(f"   ♻️  Syncing {len(to_update)} changes...")
                for lot_num, payload in to_update:
                    try:
                        client.table("lots").update(payload).match({
                            "auction_id": auction_id,
                            "lot_number": lot_num
                        }).execute()
                        print(f"      Updated Lot {lot_num}: {payload.get('status')} £{payload.get('hammer_price', '')}")
                    except Exception as e:
                        print(f"      ❌ Failed Lot {lot_num}: {e}")
            else:
                print("   ✅ No changes needed.")
                
            # Sleep
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(1, interval - elapsed)
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            print("\n🛑 Stopping sync service.")
            break
        except Exception as e:
            print(f"❌ Critical Error in loop: {e}")
            time.sleep(30) # Wait before retry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Auction Sync")
    parser.add_argument("url", help="Live auction URL")
    parser.add_argument("--auction-id", type=int, required=True, help="Auction ID")
    parser.add_argument("--interval", type=int, default=10, help="Poll interval in seconds")
    
    args = parser.parse_args()
    
    sync_loop(args.auction_id, args.url, args.interval)