#!/usr/bin/env python3
"""
Auction Scraper - Main Entry Point

Usage:
    # Pre-auction: Scrape catalogue
    python main.py catalogue "https://www.i-bidder.com/.../catalogue-id-XXX"
    
    # Post-auction: Update with results (uses same URL)
    python main.py results "https://www.i-bidder.com/.../catalogue-id-XXX"
    
    # Legacy mode: Scrape sold lots only
    python main.py scrape "https://auction-url"
"""
import sys
import argparse
import time
from scraper import scrape_auction, download_image
from catalogue_scraper import scrape_catalogue, extract_catalogue_id
from database import (
    get_client, get_or_create_auction, save_lot, upload_image,
    get_or_create_auction_by_catalogue, save_catalogue_lot, update_lot_results
)


def catalogue_command(args):
    """Pre-auction: Scrape catalogue and save to database."""
    print("=" * 60)
    print("CATALOGUE SCRAPER (Pre-Auction)")
    print("=" * 60)
    
    # Connect to Supabase
    print("\n📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    # Scrape catalogue
    print("\n🔍 Scraping auction catalogue...")
    catalogue_id, lots = scrape_catalogue(args.url)
    
    if not catalogue_id:
        print("❌ Could not extract catalogue ID from URL!")
        return
    
    if not lots:
        print("❌ No lots found in catalogue!")
        return
    
    print(f"\n✅ Found {len(lots)} catalogue lots")
    print(f"   Catalogue ID: {catalogue_id}")
    
    # Create or get auction
    print("\n📋 Creating auction record...")
    auction_id = get_or_create_auction_by_catalogue(client, catalogue_id, args.url, args.name)
    print(f"   Auction ID: {auction_id}")
    
    # Save lots to database
    print("\n💾 Saving catalogue to database...")
    saved_count = 0
    image_count = 0
    
    for i, lot in enumerate(lots):
        try:
            # Download and upload image if available
            if not args.skip_images and lot.get("image_url"):
                image_bytes = download_image(lot["image_url"])
                if image_bytes:
                    filename = f"{auction_id}_{lot['lot_number']}.jpg"
                    public_url = upload_image(image_bytes, filename)
                    lot["image_url"] = public_url
                    image_count += 1
                    time.sleep(0.1)  # Small delay between image downloads

            # Save lot to database
            save_catalogue_lot(client, auction_id, lot)
            saved_count += 1
            
            if (i + 1) % 50 == 0:
                print(f"   Saved {i + 1}/{len(lots)} lots...")
                
        except Exception as e:
            print(f"   ⚠️ Error saving lot {lot.get('lot_number')}: {e}")
    
    print("\n" + "=" * 60)
    print("CATALOGUE SCRAPE COMPLETE")
    print("=" * 60)
    print(f"   📊 Lots saved: {saved_count}")
    print(f"   🖼️ Images uploaded: {image_count}")
    print(f"   🔗 Catalogue ID: {catalogue_id}")
    print(f"   🆔 Auction ID: {auction_id}")


def results_command(args):
    """Post-auction: Scrape results and update lots."""
    print("=" * 60)
    print("RESULTS SCRAPER (Post-Auction)")
    print("=" * 60)
    
    catalogue_id = extract_catalogue_id(args.url)
    if not catalogue_id:
        print("❌ Could not extract catalogue ID from URL!")
        return
    
    print(f"\n🔗 Catalogue ID: {catalogue_id}")
    
    # Connect to Supabase
    print("\n📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    # Find existing auction
    result = client.table("auctions").select("id").eq("catalogue_id", catalogue_id).execute()
    if not result.data:
        print("❌ Auction not found! Run 'catalogue' command first.")
        return
    
    auction_id = result.data[0]["id"]
    print(f"   Auction ID: {auction_id}")
    
    # Scrape results (sold lots)
    print("\n🔍 Scraping auction results...")
    sold_lots = scrape_auction(args.url)
    
    if not sold_lots:
        print("❌ No sold lots found!")
        return
    
    print(f"\n✅ Found {len(sold_lots)} sold lots")
    
    # Update lots with results
    print("\n💾 Updating lots with results...")
    updated_count = 0
    
    for lot in sold_lots:
        try:
            # Update by lot_number (fallback since results don't have GUID)
            result = client.table("lots").update({
                "hammer_price": lot["hammer_price"],
                "price_with_premium": lot["price_with_premium"],
                "price_total": lot["price_total"],
                "status": "sold"
            }).eq("auction_id", auction_id).eq("lot_number", lot["lot_number"]).execute()
            
            if result.data:
                updated_count += 1
                
        except Exception as e:
            print(f"   ⚠️ Error updating lot {lot.get('lot_number')}: {e}")
    
    print("\n" + "=" * 60)
    print("RESULTS UPDATE COMPLETE")
    print("=" * 60)
    print(f"   📊 Lots updated: {updated_count}")


def scrape_command(args):
    """Legacy mode: Scrape sold lots only (original behavior)."""
    print("=" * 60)
    print("AUCTION SCRAPER (Legacy Mode)")
    print("=" * 60)
    
    print("\n📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    print("\n📋 Creating auction record...")
    auction_id = get_or_create_auction(client, args.url, args.name)
    print(f"   Auction ID: {auction_id}")
    
    print("\n🔍 Scraping auction data...")
    lots = scrape_auction(args.url)
    
    if not lots:
        print("❌ No sold lots found!")
        return
    
    print(f"\n✅ Found {len(lots)} sold lots")
    
    print("\n💾 Saving to database...")
    saved_count = 0
    image_count = 0
    
    for i, lot in enumerate(lots):
        try:
            if not args.skip_images and lot.get("image_url"):
                image_bytes = download_image(lot["image_url"])
                if image_bytes:
                    filename = f"{auction_id}_{lot['lot_number']}.jpg"
                    public_url = upload_image(image_bytes, filename)
                    lot["image_url"] = public_url
                    image_count += 1

            save_lot(client, auction_id, lot)
            saved_count += 1
            
            if (i + 1) % 10 == 0:
                print(f"   Saved {i + 1}/{len(lots)} lots...")
                
        except Exception as e:
            print(f"   ⚠️ Error saving lot {lot.get('lot_number')}: {e}")
    
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    print(f"   📊 Lots saved: {saved_count}")
    print(f"   🖼️ Images uploaded: {image_count}")


def backfill_command(args):
    """Bulk backfill prices from live auction page."""
    import re
    from playwright.sync_api import sync_playwright
    
    print("=" * 60)
    print("BULK BACKFILL - Scraping All Visible Sold Items")
    print("=" * 60)
    
    print("\n📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    # Fetch existing lots for this auction (to get VAT info from item names)
    existing_lots = client.table("lots").select("lot_number, item_name, vat_applicable").eq("auction_id", args.auction_id).execute()
    lot_info = {lot["lot_number"]: lot for lot in existing_lots.data}
    print(f"   Found {len(lot_info)} lots in database for Auction ID {args.auction_id}")
    
    print(f"\n🔗 Opening: {args.url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(args.url, timeout=60000)
        
        # Wait for the list to populate
        try:
            print("⏳ Waiting for lot list to load...")
            page.wait_for_selector("a.lot-info", timeout=30000)
        except:
            print("⚠️ Timed out waiting for lot list")
        
        # Scroll logic to ensuring all lazy-loaded items appear
        # (Some sites virtualize lists, but we'll try scrolling the container)
        try:
            list_area = page.locator("#lots-list-container") # Found ID from dump
            if not list_area.is_visible():
                 list_area = page.locator("#lot-list-area") # Fallback

            if list_area.is_visible():
                print("📜 Scrolling to load all lots...")
                # Scroll multiple times
                for i in range(5):
                    list_area.evaluate("el => el.scrollTop = el.scrollHeight")
                    time.sleep(1)
        except Exception as e:
            print(f"⚠️ Scroll warning: {e}")

        # Extract data using Locators
        print("📋 Extracting lot data from DOM...")
        lot_elements = page.locator("a.lot-info").all()
        print(f"   Found {len(lot_elements)} lot elements")
        
        updates = []
        for el in lot_elements:
            try:
                # Extract Lot Number
                # Text is like "4001. (Model) ..."
                # Strong tag usually holds the number "4001."
                lot_num_str = el.locator(".lot-description strong").first.inner_text().strip().replace('.', '')
                if not lot_num_str.isdigit():
                    # Fallback for complex numbers like "2001A"
                    lot_num_str = re.sub(r'[^\w]', '', lot_num_str)
                
                lot_num = lot_num_str
                
                # Extract Status
                status_el = el.locator(".status").first
                status = status_el.inner_text().strip().lower() if status_el.is_visible() else "pending"
                
                # Extract Price
                price = None
                hammer_el = el.locator(".lot-hammer").first
                if hammer_el.is_visible():
                    price_text = hammer_el.inner_text().strip()
                    # Parse "£5,000" -> 5000.0
                    match = re.search(r'[£$€]?\s*([\d,]+(?:\\.\\d{2})?)', price_text)
                    if match:
                        price = float(match.group(1).replace(',', ''))
                
                # Filter for Sold/Passed?
                # The user wants "all visible sold lots"
                if "sold" in status and price is not None:
                     updates.append({
                        "lot_number": lot_num,
                        "price": price, 
                        "status": "sold"
                     })
                # We could also capture "passed" if we wanted, but logic below focuses on sold
                
            except Exception as e:
                # Some elements might be skeletons or hidden
                continue
                
        browser.close()

    # Process updates and calculate prices
    final_updates = []
    print(f"   Extracted {len(updates)} sold lots")
    
    for u in updates:
        try:
            lot_num = u["lot_number"]
            # ... (Rest of calculation logic remains same)
            hammer_price = u["price"]
            
            # Check VAT from database info or item name
            vat_applicable = False
            if lot_num in lot_info:
                item = lot_info[lot_num]
                vat_applicable = item.get("vat_applicable", False)
                if not vat_applicable and item.get("item_name"):
                    name = item["item_name"].lower()
                    vat_applicable = '+vat' in name or '+ vat' in name
            
            # Calculate prices
            price_with_premium = round(hammer_price * 1.21, 2)  # 21% buyer's premium
            price_total = round(price_with_premium * 1.20, 2) if vat_applicable else price_with_premium
            
            final_updates.append({
                "lot_number": lot_num,
                "hammer_price": hammer_price,
                "price_with_premium": price_with_premium,
                "price_total": price_total,
                "status": "sold"
            })
        except Exception as e:
            print(f"   ⚠️ Error processing lot {lot_num}: {e}")
            continue
    
    # Batch update database
    print(f"\n💾 Updating {len(final_updates)} lots in database...")
    updated = 0
    for u in final_updates:
        lot_num = u.pop("lot_number")
        result = client.table("lots").update(u).match({
            "auction_id": args.auction_id,
            "lot_number": lot_num
        }).execute()
        if result.data:
            updated += 1
    
    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    print(f"   📊 Lots updated: {updated}/{len(final_updates)}")


def flush_command(args):
    """Reset all prices for an auction."""
    print("=" * 60)
    print("FLUSH PRICES")
    print("=" * 60)
    
    print("\n📡 Connecting to Supabase...")
    client = get_client(use_secret=True)
    
    print(f"\n🧹 Flushing prices for Auction ID: {args.auction_id}...")
    
    result = client.table("lots").update({
        "hammer_price": None,
        "price_with_premium": None,
        "price_total": None,
        "status": "not_sold"
    }).eq("auction_id", args.auction_id).execute()
    
    count = len(result.data) if result.data else 0
    
    print("\n" + "=" * 60)
    print("FLUSH COMPLETE")
    print("=" * 60)
    print(f"   📊 Lots reset: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Auction Scraper - Scrape auction catalogues and results"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Catalogue command
    cat_parser = subparsers.add_parser("catalogue", help="Scrape auction catalogue (pre-auction)")
    cat_parser.add_argument("url", help="i-bidder catalogue URL")
    cat_parser.add_argument("--name", help="Auction name", default=None)
    cat_parser.add_argument("--skip-images", action="store_true", help="Skip downloading images")
    cat_parser.set_defaults(func=catalogue_command)
    
    # Results command
    res_parser = subparsers.add_parser("results", help="Update with auction results (post-auction)")
    res_parser.add_argument("url", help="i-bidder catalogue URL")
    res_parser.set_defaults(func=results_command)
    
    # Backfill command
    backfill_parser = subparsers.add_parser("backfill", help="Bulk backfill prices from live auction page")
    backfill_parser.add_argument("url", help="Live auction URL (gaplive-eu...)")
    backfill_parser.add_argument("--auction-id", type=int, required=True, help="Auction ID in database")
    backfill_parser.set_defaults(func=backfill_command)
    
    # Flush command
    flush_parser = subparsers.add_parser("flush", help="Reset all prices for an auction")
    flush_parser.add_argument("--auction-id", type=int, required=True, help="Auction ID to flush")
    flush_parser.set_defaults(func=flush_command)
    
    # Legacy scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape sold lots only (legacy)")
    scrape_parser.add_argument("url", help="Auction URL")
    scrape_parser.add_argument("--name", help="Auction name", default=None)
    scrape_parser.add_argument("--skip-images", action="store_true", help="Skip downloading images")
    scrape_parser.set_defaults(func=scrape_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
