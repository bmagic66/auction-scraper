import json
import re
import time
import os
from playwright.sync_api import sync_playwright
from database import get_client

def handler(event, context):
    """
    Lambda handler for backfill operation.
    Expects event to contain 'body' with JSON string: {"url": "...", "auction_id": 123}
    """
    print("🚀 Lambda started")
    
    # Parse body
    body = event
    if 'body' in event:
        if isinstance(event['body'], str):
            try:
                body = json.loads(event['body'])
            except:
                pass
        else:
            body = event['body']
            
    url = body.get('url')
    auction_id = body.get('auction_id')
    
    if not url or not auction_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing url or auction_id'})
        }
        
    print(f"🔗 Processing: {url} for Auction {auction_id}")
    
    try:
        # Connect to Supabase
        client = get_client()
        
        # Fetch existing lots info to determine VAT
        existing_lots = client.table("lots").select("lot_number, item_name, vat_applicable").eq("auction_id", auction_id).execute()
        lot_info = {lot["lot_number"]: lot for lot in existing_lots.data}
        print(f"   Found {len(lot_info)} known lots")
        
        updates = []
        
        with sync_playwright() as p:
            # Launch options for Lambda
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--single-process',
                    '--no-zygote',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-setuid-sandbox'
                ]
            )
            page = browser.new_page()
            
            try:
                page.goto(url, timeout=45000)
                
                # Wait for list
                try:
                    page.wait_for_selector("a.lot-info", timeout=15000)
                except:
                    print("⚠️ Initial wait timed out, trying to proceed...")

                # Scroll to load lazy items
                try:
                    list_area = page.locator("#lots-list-container")
                    if not list_area.is_visible():
                         list_area = page.locator("#lot-list-area")
                         
                    if list_area.is_visible():
                        print("📜 Scrolling...")
                        for _ in range(3):
                            list_area.evaluate("el => el.scrollTop = el.scrollHeight")
                            time.sleep(1)
                except Exception as e:
                    print(f"⚠️ Scroll warning: {e}")
                
                # Extract
                lot_elements = page.locator("a.lot-info").all()
                print(f"   Found {len(lot_elements)} elements")
                
                for el in lot_elements:
                    try:
                        # Extract Lot Number
                        lot_num_str = el.locator(".lot-description strong").first.inner_text().strip().replace('.', '')
                        if not lot_num_str.isdigit():
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
                            match = re.search(r'[£$€]?\s*([\d,]+(?:\.\d{2})?)', price_text)
                            if match:
                                price = float(match.group(1).replace(',', ''))
                        
                        if "sold" in status and price is not None:
                            updates.append({
                                "lot_number": lot_num,
                                "price": price, 
                                "status": "sold"
                            })
                            
                    except Exception:
                        continue
                        
            finally:
                browser.close()
                print("🛑 Browser closed")

        # Process Updates
        final_updates = []
        for u in updates:
            try:
                lot_num = u["lot_number"]
                hammer_price = u["price"]
                
                # VAT Logic
                vat_applicable = False
                if lot_num in lot_info:
                    item = lot_info[lot_num]
                    vat_applicable = item.get("vat_applicable", False)
                    if not vat_applicable and item.get("item_name"):
                        name = item["item_name"].lower()
                        vat_applicable = '+vat' in name or '+ vat' in name
                
                # Calc Prices
                price_with_premium = round(hammer_price * 1.175, 2)
                price_total = round(price_with_premium * 1.20, 2) if vat_applicable else price_with_premium
                
                final_updates.append({
                    "lot_number": lot_num,
                    "hammer_price": hammer_price,
                    "price_with_premium": price_with_premium,
                    "price_total": price_total,
                    "status": "sold"
                })
            except:
                continue
        
        # Batch Update
        print(f"💾 Updating {len(final_updates)} lots...")
        success_count = 0
        for u in final_updates:
            lot_num = u.pop("lot_number")
            result = client.table("lots").update(u).match({
                "auction_id": auction_id,
                "lot_number": lot_num
            }).execute()
            if result.data:
                success_count += 1
                
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Backfill complete',
                'found': len(updates),
                'updated': success_count
            })
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
