import os
import json
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI
from inventree.part import Part,PartCategory
from inventree.stock import StockItem, StockLocation
from ebaysdk.trading import Connection


load_dotenv()

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

stock_listings_path = "stock_listings.json"
active_listings_path = "active_listings.json"

ensure_json_file(stock_listings_path)
ensure_json_file(active_listings_path)

SERVER_ADDRESS = os.environ.get('INVENTREE_SERVER_ADDRESS')
MY_USERNAME = os.environ.get('INVENTREE_USERNAME')
MY_PASSWORD = os.environ.get('INVENTREE_PASSWORD')
inventree_api = InvenTreeAPI(SERVER_ADDRESS, username=MY_USERNAME, password=MY_PASSWORD, timeout=3600)

parts = Part.list(inventree_api)
parts.sort(key=lambda x: x.IPN[:11])
data = [{'url': part.link, 'ipn': part.IPN[:11]} for part in parts if part.link]
save_data_to_json(data, stock_listings_path)

ebay_api = Connection(
    domain='api.ebay.com',
    appid=os.environ.get('EBAY_APP_ID'),
    devid=os.environ.get('EBAY_DEV_ID'),
    certid=os.environ.get('EBAY_CERT_ID'),
    token=os.environ.get('EBAY_TOKEN'),
    config_file=None
)

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

active_listings = [{'title': item.Title, 'id': item.ItemID, 'SKU': item.SKU if hasattr(item, 'SKU') else ''} for item in all_listings]
save_data_to_json(active_listings, active_listings_path)

stock_listings_data = load_data_from_json(stock_listings_path)
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
    print("Duplicates found:")
    for sku in duplicate_skus:
        print(sku)
else:
    print("No duplicates found.\n")


stock_skus = {item['ipn'] for item in stock_listings_data}
active_skus = {item['SKU'] for item in active_listings_data if item.get('SKU')}

total_comparisons = 0
total_matches = 0
missing_matches = 0

for active_item in active_listings:
    active_sku = active_item['SKU']
    active_id = active_item['id']
    active_title = active_item['title']

    if '-' in active_sku:
        main_ipn, variants = active_sku.split('-', 1)
        main_ipn = main_ipn[:11]
        active_skus.add(main_ipn)

        for variant in variants.split('-'):
            variant_length = len(variant)
            ipn_with_variant = main_ipn[:-variant_length] + variant
            total_comparisons += 1
            active_skus.add(ipn_with_variant)

            if ipn_with_variant in stock_skus:
                total_matches += 1
            else:
                missing_matches += 1
                print(f"No match found for: {active_title}")
    else:
        total_comparisons += 1

        if active_sku in stock_skus:
            total_matches += 1
        else:
            missing_matches += 1
            print(f"No match found for: {active_title}")

print(f"\nMissing matches: {missing_matches}")

missing_skus = stock_skus - active_skus
missing_skus_sorted = sorted(missing_skus)

if missing_skus_sorted:
    print("\nSKUs present in InvenTree but not active on eBay:")
    for sku in missing_skus_sorted:
        print(sku)
else:
    print("\nNo SKUs missing on eBay compared to InvenTree.")

parts_data = [{"name": part.name, "IPN": part.IPN, "ID": part.pk, "packaging": ""} for part in parts]
stock_items = StockItem.list(inventree_api)






print("\nChecking parts with no stock...")

parts_without_stock = []
all_stock_locations = StockLocation.list(inventree_api)  # Get all stock locations
all_part_categories = PartCategory.list(inventree_api)  # Get all part categories

# Create a dictionary mapping stock location names to their IDs, excluding structural locations
location_name_to_id = {location.name: location.pk for location in all_stock_locations if not getattr(location, 'structural', False)}

for part in parts:
    stock_items_for_part = [stock_item for stock_item in stock_items if stock_item.part == part.pk]

    if not stock_items_for_part:  # If no stock is found for this part
        parts_without_stock.append(part)
        print(f"No stock found for: IPN {part.IPN} - {part.name}")

        category_name = None
        try:
            if part.category:  # If the part has an assigned category (part.category is an ID)
                # Find the category in the list of part categories
                category = next((cat for cat in all_part_categories if cat.pk == part.category), None)

                if category:
                    category_name = category.name  # Retrieve the category name
                    print(f"Category for part IPN {part.IPN}: {category_name}")
                else:
                    print(f"Category with ID {part.category} not found for part IPN {part.IPN}.")
            else:
                print(f"No category assigned for part IPN {part.IPN}.")
        except Exception as e:
            print(f"Error fetching category for part IPN {part.IPN}. Details: {e}")

        # Find the matching stock location based on the category name
        matching_location = None
        if category_name:
            if category_name in location_name_to_id:
                matching_location = next(location for location in all_stock_locations if location.name == category_name)
                print(f"Found matching location for category '{category_name}': {matching_location.name} (ID: {matching_location.pk})")
            else:
                print(f"No matching stock location found for category '{category_name}'.")

        if not matching_location:
            print(f"No valid stock location found for part IPN {part.IPN}. Skipping stock creation.")
            continue

        try:
            stock_data = {
                "part": part.pk,                 # Link the stock item to the part
                "location": matching_location.pk,  # Specify the part's location
                "quantity": 1,                   # Set the initial quantity to 1
                "status": 10,                    # Stock status (adjust as per InvenTree configuration)
            }

            print(f"Creating stock item with data: {stock_data}")

            new_stock_item = StockItem.create(inventree_api, stock_data)
            print(f"Empty stock created for: IPN {part.IPN} - {part.name}, Stock ID: {new_stock_item.pk}")

        except Exception as e:
            print(f"Error creating stock for: IPN {part.IPN} - {part.name}. Details: {e}")

print(f"\nTotal parts with no initial stock: {len(parts_without_stock)}")

















for item in parts_data:
    part_ipn = item['IPN']
    part_obj = next((part for part in parts if part.IPN == part_ipn), None)

    if part_obj:
        stock_items_for_part = [stock_item for stock_item in stock_items if stock_item.part == part_obj.pk]

        if stock_items_for_part:
            item['packaging'] = stock_items_for_part[0].packaging



missing_packaging_count = 0
print("\nParts Without Packaging:")


for part in parts_data:
    if not part['packaging']:
        missing_packaging_count += 1
        print(f"IPN: {part['IPN']}")

print(f"\nTotal Parts Without Packaging: {missing_packaging_count}")
