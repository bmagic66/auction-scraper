"""
Catalogue scraper for i-bidder.com auctions.
Scrapes all lots from an auction catalogue before sale day.
"""
import re
import time
from playwright.sync_api import sync_playwright, Page


def extract_catalogue_id(url: str) -> str | None:
    """Extract catalogue ID from i-bidder URL."""
    match = re.search(r'catalogue-id-([a-zA-Z0-9]+)', url)
    return match.group(1) if match else None


def scroll_to_load_all(page: Page, max_scrolls: int = 200):
    """Scroll page to load all items via infinite scroll."""
    previous_count = 0
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        # Count loaded items
        items = page.locator(".lot-single").all()
        current_count = len(items)
        
        if current_count == previous_count and current_count > 0:
            # No new items loaded after attempts, we're done
            scroll_count += 1
            if scroll_count > 3: # Wait up to 3 scroll attempts
               break
        else:
             if current_count > previous_count:
                 scroll_count = 0  # Reset counter when new items load
             else:
                 scroll_count += 1
        
        previous_count = current_count
        
        # Scroll down to bottom of page
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        # Determine wait time - if finding lots, wait longer for load
        time.sleep(1.0) 
        
        # Also try to click "Load More" if it exists? (Not observed in logs, but common)
    
    print(f"Loaded {previous_count} items")
    return previous_count


def extract_catalogue_data(page: Page) -> list:
    """Extract all lot data from the catalogue page."""
    lots = []
    
    # Use the new selector
    lot_elements = page.locator(".lot-single").all()
    
    print(f"Extracting data from {len(lot_elements)} elements...")

    for lot_elem in lot_elements:
        try:
            # We extraction using a simpler approach per element rather than a complex eval script, 
            # or update the eval to match the new structure.
            lot_data = lot_elem.evaluate(r"""
                (el) => {
                    const result = {
                        lotNumber: null,
                        itemName: null,
                        imageUrl: null,
                        lotUrl: null,
                        lotGuid: null
                    };
                    
                    // Image
                    const img = el.querySelector('.thumb img');
                    if (img) {
                        let src = img.src || img.getAttribute('data-src');
                        if (src) {
                            // Remove query string (e.g. ?h=175) to get full size
                            result.imageUrl = src.split('?')[0];
                        }
                    }
                    
                    // Lot number
                    const numberDiv = el.querySelector('.lot-number') || el.querySelector('.number');
                    if (numberDiv) {
                        // Extract just number
                        result.lotNumber = numberDiv.textContent.replace('Lot', '').trim();
                    }
                    
                    // Title/Link
                    const link = el.querySelector('.lot-header h3 a') || el.querySelector('.lot-title');
                    if (link) {
                        result.itemName = link.textContent.trim();
                        if (link.href) {
                           result.lotUrl = link.href;
                           // Extract GUID
                           const guidMatch = link.href.match(/\/lot-([a-f0-9-]+)/);
                           if (guidMatch) {
                               result.lotGuid = guidMatch[1];
                           }
                        }
                    }
                    
                    return result;
                }
            """)
            
            if not lot_data.get('lotNumber'):
                # Try fallback for number if JS extraction failed or structure varied
                continue
            
            # Detect VAT in item name
            item_name = lot_data['itemName'] or ""
            vat_applicable = '+vat' in item_name.lower() or '+ vat' in item_name.lower()
            
            lots.append({
                "lot_number": lot_data['lotNumber'],
                "item_name": item_name,
                "image_url": lot_data['imageUrl'],
                "lot_url": lot_data['lotUrl'],
                "lot_guid": lot_data['lotGuid'],
                "vat_applicable": vat_applicable,
                "status": "pending"
            })
            
        except Exception as e:
            print(f"Error processing lot: {e}")
            continue
    
    return lots



def scrape_catalogue(url: str) -> tuple[str | None, list]:
    """
    Scrape all lots from an i-bidder auction catalogue.
    Returns (catalogue_id, list of lot dictionaries).
    """
    catalogue_id = extract_catalogue_id(url)
    print(f"Scraping catalogue: {catalogue_id}")
    print(f"URL: {url}")
    
    # Use a real user agent to bypass WAF
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    
    all_lots = []
    
    with sync_playwright() as p:
        # Launch with arguments to reduce bot detection
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox', 
                '--disable-setuid-sandbox',
            ]
        )
        
        # Create a context with the user agent and other bypass settings
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale="en-GB"
        )
        
        # Hide webdriver property
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        
        # Navigate to catalogue
        try:
            print(f"Navigating to first page...")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for content to load - handling potential WAF challenge
            print("Waiting for page content to load...")
            try:
                # Wait up to 30 seconds for specific content to appear
                # The WAF challenge might take a while to redirect/reload
                page.wait_for_selector(".lot-single", timeout=30000)
                print("Content loaded successfully.")
            except Exception:
                print("Content selector not found immediately. Checking for WAF/Captcha...")
                # Could be a captcha or just slow
                time.sleep(5) 
                
        except Exception as e:
            print(f"Navigation error: {e}")
            return catalogue_id, []
            
        page_num = 1
        while True:
            # Extract lots from current page
            page_lots = extract_catalogue_data(page)
            if page_lots:
                all_lots.extend(page_lots)
                print(f"Page {page_num}: Found {len(page_lots)} lots (Total: {len(all_lots)})")
            else:
                print(f"Page {page_num}: No lots found")
            
            # Look for "Next" button - usually a link with rel="next" or class containing "next"
            # Debug output showed 'a[rel="next"]' exists
            next_link = page.locator("a[rel='next']").first
            
            if next_link.count() > 0 and next_link.is_visible():
                print(f"Navigating to page {page_num + 1}...")
                
                # Get the URL to be safe, or click
                # Creating a new wait cycle
                with page.expect_navigation(wait_until="domcontentloaded"):
                    next_link.click()
                
                # Small random delay to be polite and avoid detection
                time.sleep(2)
                page_num += 1
            else:
                print("No more pages found.")
                break
        
        browser.close()
    
    print(f"Found {len(all_lots)} catalogue lots total")
    return catalogue_id, all_lots
