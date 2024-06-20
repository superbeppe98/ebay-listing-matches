import os
import json
from dotenv import load_dotenv
import logging
from inventree.api import InvenTreeAPI
from inventree.part import Part
from inventree.stock import StockItem
from ebaysdk.trading import Connection

load_dotenv()

# Configura il logging
logging.basicConfig(filename='debug.log', filemode='w', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


def ensure_json_file(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)

def save_data_to_json(data, path):
    with open(path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def load_data_from_json(path):
    if os.path.exists(path):
        with open(path, 'r') as json_file:
            return json.load(json_file)
    return []

# File paths
stock_listings_path = "stock_listings.json"
active_listings_path = "active_listings.json"

# Ensure JSON files exist
ensure_json_file(stock_listings_path)
ensure_json_file(active_listings_path)

# InvenTree API connection
SERVER_ADDRESS = os.environ.get('INVENTREE_SERVER_ADDRESS')
MY_USERNAME = os.environ.get('INVENTREE_USERNAME')
MY_PASSWORD = os.environ.get('INVENTREE_PASSWORD')
inventree_api = InvenTreeAPI(SERVER_ADDRESS, username=MY_USERNAME, password=MY_PASSWORD, timeout=3600)

# Retrieve parts from InvenTree and save data to stock_listings.json
parts = Part.list(inventree_api)
parts.sort(key=lambda x: x.IPN)
data = [{'url': part.link, 'ipn': part.IPN[:11]} if part.link else {'url': '', 'ipn': part.IPN[:11]} for part in parts]
save_data_to_json(data, stock_listings_path)

# eBay API connection
ebay_api = Connection(
    domain='api.ebay.com',
    appid=os.environ.get('EBAY_APP_ID'),
    devid=os.environ.get('EBAY_DEV_ID'),
    certid=os.environ.get('EBAY_CERT_ID'),
    token=os.environ.get('EBAY_TOKEN'),
    config_file=None
)

# Retrieve active listings from eBay
page_number = 1
entries_per_page = 200
all_listings = []

while True:
    response = ebay_api.execute('GetMyeBaySelling', {
        'ActiveList': {
            'Include': True,
            'Pagination': {
                'PageNumber': page_number,
                'EntriesPerPage': entries_per_page
            }
        }
    })

    items = response.reply.ActiveList.ItemArray.Item
    all_listings.extend(items)

    pagination_result = response.reply.ActiveList.PaginationResult
    total_pages = int(pagination_result.TotalNumberOfPages)
    page_number += 1

    if page_number > total_pages:
        break

# Save active listings to active_listings.json
active_listings = [{'title': item.Title, 'id': item.ItemID, 'SKU': item.SKU if hasattr(item, 'SKU') else ''} for item in all_listings]
save_data_to_json(active_listings, active_listings_path)

# Check for duplicate SKUs
active_listings_data = load_data_from_json(active_listings_path)
seen_skus = set()
duplicate_skus = set()

for item in active_listings_data:
    ebay_sku = item.get('SKU', '')
    if ebay_sku:
        if ebay_sku in seen_skus:
            duplicate_skus.add(ebay_sku)
        else:
            seen_skus.add(ebay_sku)

if duplicate_skus:
    print(f"Duplicati trovati: {duplicate_skus}")
else:
    print("Check SKU Completed.")


# Carica i dati dai file JSON
stock_listings_data = load_data_from_json(stock_listings_path)
active_listings_data = load_data_from_json(active_listings_path)


# Conteggio degli SKU negli active listings
total_active_listings = len(active_listings_data)

# Conteggio degli SKU negli stock listings
total_stock_listings = len(stock_listings_data)

# Stampiamo i risultati
print(f"Total active listings: {total_active_listings}")
print(f"Total stock listings: {total_stock_listings}")
































# Inizializzazione del conteggio dei confronti
total_comparisons = 0
total_matches = 0
missing_matches = 0

# Iterazione sugli SKU negli active listings
for active_item in active_listings:
    active_sku = active_item['SKU']
    active_id = active_item['id']
    active_title = active_item['title']

    # Debug: Log dell'inizio del processo per l'SKU attuale
    logging.info(f"Processing SKU: {active_sku} ({active_title})")

    # Controlla se l'SKU attivo ha varianti
    if '-' in active_sku:
        main_ipn, variants = active_sku.split('-', 1)
        main_ipn = main_ipn[:11]  # Mantieni solo i primi 11 caratteri

        # Debug: Log dell'SKU principale e delle sue varianti
        logging.info(f"Main IPN: {main_ipn}, Variants: {variants}")

          # Split delle varianti e elaborazione
        for variant in variants.split('-'):
            variant_length = len(variant)
            ipn_with_variant = main_ipn[:-variant_length] + variant
            total_comparisons += 1  # Ogni combinazione di IPN e variante conta come un confronto

            # Debug: Log della variante attualmente processata
            logging.info(f"Processing variant: {variant}")

            # Controlla se esiste una corrispondenza negli stock listings
            matched = False
            for stock_item in stock_listings_data:
                stock_ipn = stock_item['ipn']
                stock_url = stock_item['url']
                if ipn_with_variant == stock_ipn:
                    matched = True
                    total_matches += 1
                    # Debug: Log della corrispondenza trovata
                    logging.info(f"Match found for SKU '{active_sku}' ({active_title}), IPN: {stock_ipn}, URL: {stock_url}")
                    break
            
            if not matched:
                missing_matches += 1
                # Debug: Log della mancata corrispondenza
                logging.warning(f"No match found for SKU '{active_sku}' ({active_title}), IPN with variant: {ipn_with_variant}")

    else:
        total_comparisons += 1  # Conta l'SKU principale come un confronto

        # Debug: Log dell'SKU principale
        logging.info(f"Main IPN: {active_sku}")

        # Controlla se l'SKU principale ha una corrispondenza negli stock listings
        matched = False
        for stock_item in stock_listings_data:
            stock_ipn = stock_item['ipn']
            stock_url = stock_item['url']
            if active_sku == stock_ipn:
                matched = True
                total_matches += 1
                # Debug: Log della corrispondenza trovata
                logging.info(f"Match found for SKU '{active_sku}' ({active_title}), IPN: {stock_ipn}, URL: {stock_url}")
                break
        
        if not matched:
            missing_matches += 1
            # Debug: Log della mancata corrispondenza
            logging.warning(f"No match found for SKU '{active_sku}' ({active_title}), IPN: {active_sku}")

# Stampiamo i risultati
print(f"\nComparison check completed.")
print(f"Total comparisons: {total_comparisons}")
print(f"Total matches: {total_matches}")
print(f"Missing matches: {missing_matches}")































# Request the list of parts through the API
parts = Part.list(inventree_api)

# Order the list of parts by IPN
parts.sort(key=lambda x: str(x.IPN))

# Prepare a list of dictionaries for parts data
parts_data = [{"name": part.name, "IPN": part.IPN,
               "ID": part.pk, "packaging": ""} for part in parts]

# Retrieve all stock items through the API
stock_items = StockItem.list(inventree_api)

# Update the JSON with the "packaging" field from the StockItems API
for item in parts_data:
    part_ipn = item['IPN']
    part_obj = next((part for part in parts if part.IPN == part_ipn), None)

    if part_obj:
        stock_items_for_part = [
            stock_item for stock_item in stock_items if stock_item.part == part_obj.pk]

        if stock_items_for_part:
            stock_item = stock_items_for_part[0]
            item['packaging'] = stock_item.packaging

# Print the parts without packaging
print("\nParts Without Packaging:")
missing_packaging_found = False
missing_packaging_count = 0  # Initialize the counter

for part in parts_data:
    if not part['packaging']:
        missing_packaging_found = True
        missing_packaging_count += 1  # Increment the counter
        print(f"IPN: {part['IPN']} - Without Packaging")

if missing_packaging_found:
    print(
        f"\nParts Without Packaging check completed. Total Parts Without Packaging: {missing_packaging_count}")
else:
    print("\nParts Without Packaging check completed. No Parts Without Packaging")
