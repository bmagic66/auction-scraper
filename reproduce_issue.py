
import time
from playwright.sync_api import sync_playwright

url = "https://www.i-bidder.com/en-gb/auction-catalogues/peacock-auctioneers/catalogue-id-whpav12620"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox', 
                '--disable-setuid-sandbox',
            ]
        )
        
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale="en-GB"
        )
        
        # Add init script to hide webdriver property
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        
        print(f"Navigating to {url}...")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"Navigation error: {e}")
            
        print("Waiting for potential WAF challenge/reload (20s)...")
        time.sleep(20)
        
        # Check title again
        print(f"Page Title after wait: {page.title()}")
        
        # Check for items again
        items = page.locator(".lot-single").all()
        print(f"Found {len(items)} items with selector '.lot-single'")
        
        if len(items) == 0:
             # Check for other potential classes
            potential_classes = [".lot", ".search-result", ".lot-item", "div[id^='lot']", ".lot_row"]
            for cls in potential_classes:
                count = page.locator(cls).count()
                print(f"Selector '{cls}': {count} matches")
            
            # Dump if still failing
            with open("debug_page_3.html", "w") as f:
                f.write(page.content())
            print("Dumped content to debug_page_3.html")
        else:
            print("SUCCESS: Items found!")

        browser.close()

if __name__ == "__main__":
    run()
