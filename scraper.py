"""
Playwright-based scraper for Global Auction Platform auctions.
Extracts sold items only with their images, names, and prices.
"""
import re
import time
import requests
from playwright.sync_api import sync_playwright, Page


def scroll_to_load_all(page: Page, container_selector: str, max_scrolls: int = 100):
    """Scroll container to load all items via infinite scroll."""
    container = page.locator(container_selector)
    previous_count = 0
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        # Get current item count
        items = page.locator(".lot-info").all()
        current_count = len(items)
        
        if current_count == previous_count:
            # No new items loaded, we're done
            break
        
        previous_count = current_count
        scroll_count += 1
        
        # Scroll down
        container.evaluate("el => el.scrollTop = el.scrollHeight")
        time.sleep(0.5)  # Wait for content to load
    
    print(f"Loaded {previous_count} items after {scroll_count} scrolls")
    return previous_count


def extract_lot_data(page: Page) -> list:
    """Extract all sold lot data from the page."""
    lots = []
    
    # Get all lot-info elements
    lot_elements = page.locator(".lot-info").all()
    
    for i, lot_elem in enumerate(lot_elements):
        try:
            # Use JavaScript to extract all data from the lot element
            # Structure: lot-info > div(contains Sold + price) > [div(Sold), div(£price)]
            #            lot-info > div(image) > img
            #            lot-info > div > strong(lot#) + text(name)
            
            lot_data = lot_elem.evaluate("""
                (el) => {
                    const result = {
                        isSold: false,
                        soldPrice: null,
                        lotNumber: null,
                        itemName: null,
                        imageUrl: null
                    };
                    
                    // Get all direct child divs
                    const divs = el.querySelectorAll(':scope > div');
                    
                    for (const div of divs) {
                        const text = div.textContent.trim();
                        
                        // Check if this div contains "Sold" status
                        if (text.startsWith('Sold')) {
                            result.isSold = true;
                            // Price is usually in a child div like "£130"
                            const priceMatch = text.match(/£([\\d,]+(?:\\.\\d{2})?)/);
                            if (priceMatch) {
                                result.soldPrice = parseFloat(priceMatch[1].replace(',', ''));
                            }
                        }
                        
                        // Check for image
                        const img = div.querySelector('img');
                        if (img && img.src) {
                            result.imageUrl = img.src;
                        }
                        
                        // Check for lot number (in strong tag)
                        const strong = div.querySelector('strong');
                        if (strong) {
                            const lotMatch = strong.textContent.match(/(\\d+)\\./);
                            if (lotMatch) {
                                result.lotNumber = lotMatch[1];
                                // Item name is the rest of the text after the strong tag
                                const nameText = div.textContent.replace(strong.textContent, '').trim();
                                result.itemName = nameText;
                            }
                        }
                    }
                    
                    return result;
                }
            """)
            
            # Only include sold items
            if not lot_data.get('isSold') or not lot_data.get('soldPrice'):
                continue
            
            if not lot_data.get('lotNumber'):
                continue
            
            # Detect VAT in item name
            item_name = lot_data['itemName'] or ""
            vat_applicable = '+vat' in item_name.lower() or '+ vat' in item_name.lower()
            
            # Calculate prices
            hammer_price = lot_data['soldPrice']
            price_with_premium = round(hammer_price * 1.21, 2)  # +21% buyer's premium
            price_total = round(price_with_premium * 1.20, 2) if vat_applicable else price_with_premium  # +20% VAT
            
            lots.append({
                "lot_number": lot_data['lotNumber'],
                "item_name": item_name,
                "hammer_price": hammer_price,
                "price_with_premium": price_with_premium,
                "price_total": price_total,
                "currency": "GBP",
                "vat_applicable": vat_applicable,
                "image_url": lot_data['imageUrl']
            })
            
        except Exception as e:
            print(f"Error processing lot: {e}")
            continue
    
    return lots


def download_image(url: str) -> bytes | None:
    """Download image from URL. Returns bytes or None on failure."""
    if not url:
        return None
    
    # Strip query string to get full-size image
    clean_url = url.split('?')[0]
    
    try:
        response = requests.get(clean_url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Failed to download image {clean_url}: {e}")
        return None


def scrape_auction(url: str) -> list:
    """
    Scrape all sold lots from an auction URL.
    Returns list of lot dictionaries with: lot_number, item_name, sold_price, currency, image_url
    """
    print(f"Scraping auction: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate to auction
        page.goto(url, wait_until="networkidle")
        time.sleep(2)  # Extra wait for dynamic content
        
        # Scroll to load all items
        scroll_to_load_all(page, "#lot-list-area")
        
        # Extract lot data
        lots = extract_lot_data(page)
        
        browser.close()
    
    print(f"Found {len(lots)} sold lots")
    return lots
