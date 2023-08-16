import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from inventree.api import InvenTreeAPI
from inventree.part import Part
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
import json

load_dotenv()

path = "stock_listings.json"

if not os.path.exists(path):
    open(path, "w").close()

active_listings_path = "active_listings.json"

if not os.path.exists(active_listings_path):
    open(active_listings_path, "w").close()

SERVER_ADDRESS = os.environ.get('INVENTREE_SERVER_ADDRESS')
MY_USERNAME = os.environ.get('INVENTREE_USERNAME')
MY_PASSWORD = os.environ.get('INVENTREE_PASSWORD')
api = InvenTreeAPI(SERVER_ADDRESS, username=MY_USERNAME,
                   password=MY_PASSWORD, timeout=3600)

parts = Part.list(api)
parts.sort(key=lambda x: x.IPN)

data = [{'url': part.link, 'ipn': part.IPN} if part.link else {
    'url': '', 'ipn': part.IPN} for part in parts]

with open(path, 'w') as json_file:
    json.dump(data, json_file, indent=4)

api = Trading(
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
    response = api.execute('GetMyeBaySelling', {
        'ActiveList': {
            'Include': True,
            'Pagination': {
                'PageNumber': page_number,
                'EntriesPerPage': entries_per_page
            }
        }
    })

    if response.reply.ActiveList is None:
        break

    all_listings.extend(response.reply.ActiveList.ItemArray.Item)

    if int(response.reply.ActiveList.PaginationResult.TotalNumberOfPages) > page_number:
        page_number += 1
    else:
        break

active_listings = [{'title': item.Title, 'id': item.ItemID,
                    'SKU': item.SKU if hasattr(item, 'SKU') else ''} for item in all_listings]

with open(active_listings_path, 'w') as f:
    json.dump(active_listings, f)

with open('active_listings.json', 'r') as json_file:
    active_listings_data = json.load(json_file)

seen_skus = set()

for item in active_listings_data:
    ebay_sku = item.get('SKU', '')
    if ebay_sku:
        if ebay_sku in seen_skus:
            print(f"Duplicate found: {ebay_sku}")
        else:
            seen_skus.add(ebay_sku)

print("\nDuplicate SKU check completed.\n")

with open('stock_listings.json', 'r') as json_file:
    stock_listings_data = json.load(json_file)

mapping = {item['ipn']: item['url'] for item in stock_listings_data}

total_matches = 0
total_comparisons = 0
incorrect_matches = 0

for ebay_item in active_listings_data:
    ebay_sku = ebay_item.get('SKU', '')
    if ebay_sku:
        total_comparisons += 1
        ipn = None
        url = None

        if '-' in ebay_sku:
            main_ipn, variants = ebay_sku.split('-', 1)
            if main_ipn in mapping:
                ipn = main_ipn
                url = mapping[main_ipn]
                for variant in variants.split('-'):
                    ipn_with_variant = ipn + variant
                    if ipn_with_variant in mapping:
                        ipn = ipn_with_variant
                        url = mapping[ipn_with_variant]
                        break
        elif ebay_sku in mapping:
            ipn = ebay_sku
            url = mapping[ebay_sku]

        if ipn and url:
            total_matches += 1
        else:
            print(f"No match found for SKU {ebay_sku}")

print(
    f"\nComparison completed. Total comparisons: {total_comparisons}, Total matches: {total_matches}, Missing matches: {total_comparisons-total_matches}, Incorrect matches: {incorrect_matches}\n")

part_mapping = {part['ipn']: part['url'] for part in stock_listings_data}


correct_links = 0
missing_links = 0

matching_details = []
skus_without_link = set()

for ebay_item in active_listings_data:
    ebay_sku = ebay_item.get('SKU', '')
    ebay_id = ebay_item.get('id', '')
    ebay_url = f"https://www.ebay.it/itm/{ebay_id}"

    if ebay_sku:
        ipn = None
        url = None

        if '-' in ebay_sku:
            main_ipn, variants = ebay_sku.split('-', 1)
            if main_ipn in part_mapping:
                ipn = main_ipn
                url = part_mapping[main_ipn]

                for variant in variants.split('-'):
                    ipn_with_variant = ipn + variant
                    if ipn_with_variant in part_mapping:
                        ipn = ipn_with_variant
                        url = part_mapping[ipn_with_variant]
                        break
            else:
                found_variant = False
                for variant in variants.split('-'):
                    ipn_with_variant = main_ipn + variant
                    if ipn_with_variant in part_mapping:
                        found_variant = True
                        ipn = ipn_with_variant
                        url = part_mapping[ipn_with_variant]
                        break

                if not found_variant:
                    ipn = None
                    url = None
        else:
            ipn = ebay_sku
            url = part_mapping.get(ebay_sku)

        if ipn and url:
            if ebay_url == url:
                correct_links += 1
                # matching_details.append({'ebay_url': ebay_url, 'ipn': ipn, 'match_status': 'Match'})
            else:
                incorrect_matches += 1
                matching_details.append(
                    {'ebay_url': ebay_url, 'ipn': ipn, 'match_status': 'Not a match'})
        else:
            missing_links += 1
            skus_without_link.add(ebay_sku)
            matching_details.append(
                {'ebay_url': ebay_url, 'ipn': ebay_sku, 'match_status': 'Missing'})

missing_links += len(skus_without_link)

matching_details_sorted = sorted(matching_details, key=lambda x: x['ipn'])
ipns_without_match = []

for part in stock_listings_data:
    ipn = part.get('ipn', '')
    sku = part_mapping.get(ipn, '')

    if not sku:
        missing_links += 1
        ipns_without_match.append(ipn)

for match in matching_details_sorted:
    print(
        f"eBay URL: {match['ebay_url']} - IPN: {match['ipn']} - {match['match_status']} on Inventree URL")

print("\nIPNs without a match:")
for ipn in ipns_without_match:
    print(f"IPN: {ipn} - Not mapped on eBay")

print(
    f"\nLinks Comparison completed. Correct links: {correct_links}, Missing links: {missing_links}")
