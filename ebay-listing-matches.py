import os
import json
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI
from inventree.part import Part, PartCategory
from inventree.stock import StockItem, StockLocation
from ebaysdk.trading import Connection

# Load environment variables from a .env file
load_dotenv()

# Function to ensure a JSON file exists. If not, it creates an empty list inside it.
def ensure_json_file(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)

# Function to save data to a JSON file
def save_data_to_json(data, path):
    with open(path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

# Function to load data from a JSON file
def load_data_from_json(path):
    if os.path.exists(path):
        with open(path, 'r') as json_file:
            return json.load(json_file)
    return []

# Paths for storing JSON data related to stock and active listings
stock_listings_path = "stock_listings.json"
active_listings_path = "active_listings.json"

# Ensure the JSON files exist
ensure_json_file(stock_listings_path)
ensure_json_file(active_listings_path)

# Get the InvenTree server address and credentials from environment variables
SERVER_ADDRESS = os.environ.get('INVENTREE_SERVER_ADDRESS')
MY_USERNAME = os.environ.get('INVENTREE_USERNAME')
MY_PASSWORD = os.environ.get('INVENTREE_PASSWORD')

# Initialize InvenTree API client with credentials
inventree_api = InvenTreeAPI(SERVER_ADDRESS, username=MY_USERNAME, password=MY_PASSWORD, timeout=3600)

# Fetch all parts from InvenTree and sort by their IPN (internal part number)
parts = Part.list(inventree_api)
parts.sort(key=lambda x: x.IPN[:11])

# Prepare a list of parts containing URLs and truncated IPNs, and save it to a JSON file
data = [{'url': part.link, 'ipn': part.IPN[:11]} for part in parts if part.link]
save_data_to_json(data, stock_listings_path)

# Initialize eBay API connection using environment variables
ebay_api = Connection(
    domain='api.ebay.com',
    appid=os.environ.get('EBAY_APP_ID'),
    devid=os.environ.get('EBAY_DEV_ID'),
    certid=os.environ.get('EBAY_CERT_ID'),
    token=os.environ.get('EBAY_TOKEN'),
    config_file=None
)

# Initialize variables for paginating through eBay listings
page_number = 1
entries_per_page = 200
all_listings = []

# Loop to retrieve all active eBay listings
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

    # Break the loop if all pages are fetched
    if page_number > total_pages:
        break

# Prepare active listings data with titles, IDs, and SKUs, then save to a JSON file
active_listings = [{'title': item.Title, 'id': item.ItemID, 'SKU': item.SKU if hasattr(item, 'SKU') else ''} for item in all_listings]
save_data_to_json(active_listings, active_listings_path)

# Load the stock and active listings data from JSON files
stock_listings_data = load_data_from_json(stock_listings_path)
active_listings_data = load_data_from_json(active_listings_path)

# Initialize sets to keep track of seen and duplicate SKUs
seen_skus = set()
duplicate_skus = set()

# Check for duplicate SKUs in eBay active listings
for item in active_listings_data:
    ebay_sku = item.get('SKU', '')
    if ebay_sku:
        if ebay_sku in seen_skus:
            duplicate_skus.add(ebay_sku)
        else:
            seen_skus.add(ebay_sku)

# Print duplicate SKUs if found
if duplicate_skus:
    print("Duplicates found:")
    for sku in duplicate_skus:
        print(sku)
else:
    print("No duplicates found.\n")

# Create sets of SKUs from stock listings and active eBay listings
stock_skus = {item['ipn'] for item in stock_listings_data}
active_skus = {item['SKU'] for item in active_listings_data if item.get('SKU')}

# Initialize counters for comparisons, matches, and missing matches
total_comparisons = 0
total_matches = 0
missing_matches = 0

# Compare SKUs between active eBay listings and stock listings
for active_item in active_listings:
    active_sku = active_item['SKU']
    active_id = active_item['id']
    active_title = active_item['title']

    if '-' in active_sku:
        # Handle variant SKUs by splitting and checking each variant
        main_ipn, variants = active_sku.split('-', 1)
        main_ipn = main_ipn[:11]
        active_skus.add(main_ipn)

        for variant in variants.split('-'):
            variant_length = len(variant)
            ipn_with_variant = main_ipn[:-variant_length] + variant
            total_comparisons += 1
            active_skus.add(ipn_with_variant)

            # Check if the variant SKU is in stock
            if ipn_with_variant in stock_skus:
                total_matches += 1
            else:
                missing_matches += 1
                print(f"No match found for: {active_title}")
    else:
        total_comparisons += 1

        # Check if the SKU is in stock
        if active_sku in stock_skus:
            total_matches += 1
        else:
            missing_matches += 1
            print(f"No match found for: {active_title}")

# Print results of missing matches
print(f"\nMissing matches: {missing_matches}")

# Determine SKUs present in InvenTree but not on eBay
missing_skus = stock_skus - active_skus
missing_skus_sorted = sorted(missing_skus)

# Print missing SKUs
if missing_skus_sorted:
    print("\nSKUs present in InvenTree but not active on eBay:")
    for sku in missing_skus_sorted:
        print(sku)
else:
    print("\nNo SKUs missing on eBay compared to InvenTree.")

# Prepare parts data for stock items without packaging
parts_data = [{"name": part.name, "IPN": part.IPN, "ID": part.pk, "packaging": ""} for part in parts]
stock_items = StockItem.list(inventree_api)

# Check for parts that have no stock and create stock items for them
print("\nChecking parts with no stock...")

parts_without_stock = []
all_stock_locations = StockLocation.list(inventree_api)
all_part_categories = PartCategory.list(inventree_api)

# Map location names to IDs
location_name_to_id = {location.name: location.pk for location in all_stock_locations if not getattr(location, 'structural', False)}

# Create empty stock items for parts with no stock
for part in parts:
    stock_items_for_part = [stock_item for stock_item in stock_items if stock_item.part == part.pk]

    if not stock_items_for_part:
        parts_without_stock.append(part)
        print(f"No stock found for: IPN {part.IPN} - {part.name}")

        # Assign location based on category if available
        category_name = None
        if part.category:
            category = next((cat for cat in all_part_categories if cat.pk == part.category), None)
            if category:
                category_name = category.name

        matching_location = None
        if category_name:
            if category_name in location_name_to_id:
                matching_location = next(location for location in all_stock_locations if location.name == category_name)

            stock_data = {
                "part": part.pk,
                "location": matching_location.pk,
                "quantity": 1,
                "status": 10, 
            }
        # Create the new stock item
        new_stock_item = StockItem.create(inventree_api, stock_data)
        print(f"Empty stock created for: IPN {part.IPN} - {part.name}, Stock ID: {new_stock_item.pk}")
        
print(f"Total parts with no initial stock: {len(parts_without_stock)}")

# Update parts data with packaging information from stock items
for item in parts_data:
    part_ipn = item['IPN']
    part_obj = next((part for part in parts if part.IPN == part_ipn), None)

    if part_obj:
        stock_items_for_part = [stock_item for stock_item in stock_items if stock_item.part == part_obj.pk]

        if stock_items_for_part:
            item['packaging'] = stock_items_for_part[0].packaging

# Print out parts that are missing packaging information
missing_packaging_count = 0
print("\nParts Without Packaging:")

for part in parts_data:
    if not part['packaging']:
        missing_packaging_count += 1
        print(f"IPN: {part['IPN']}")

# Final count of parts missing packaging
print(f"\nTotal Parts Without Packaging: {missing_packaging_count}")
