
from catalogue_scraper import scrape_catalogue

url = "https://www.i-bidder.com/en-gb/auction-catalogues/peacock-auctioneers/catalogue-id-whpav12620"

print(f"Testing fixed scraper on {url}...")
catalogue_id, lots = scrape_catalogue(url)

print(f"Catalogue ID: {catalogue_id}")
print(f"Found {len(lots)} lots.")

if len(lots) > 0:
    print("SUCCESS: Fix verified!")
    print(f"First lot sample: {lots[0]}")
else:
    print("FAILURE: No lots found.")
