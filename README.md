# eBay Listing Matcher
The eBay Listing Matcher is a Python script designed to compare and match eBay listings with parts from an Inventree instance. This script utilizes the eBay Trading API and the Inventree API to gather and process data.

## Installation
Before using the eBay Listing Matcher, ensure that you have Python 3 installed on your system. Additionally, install the required dependencies by running the following command:
```shell
pip install -r requirements.txt
```

## Usage
Set up the necessary environment variables for connecting to your InvenTree server. Make sure to replace YOUR_SERVER_ADDRESS, YOUR_USERNAME, and YOUR_PASSWORD with the appropriate values:

```shell
export INVENTREE_SERVER_ADDRESS=YOUR_SERVER_ADDRESS
export INVENTREE_USERNAME=YOUR_USERNAME
export INVENTREE_PASSWORD=YOUR_PASSWORD
```

Run the script ebay_listing_matcher.py:

```shell
python3 ebay_listing_matcher.py
```

The script will perform the following tasks:

Fetch data from your Inventree server and create a JSON file stock_listings.json containing the part information.
Fetch active eBay listings using the eBay Trading API and create a JSON file active_listings.json containing listing details.
Check for duplicate SKUs in the eBay listings.
Compare eBay listings with Inventree part data to find matches based on SKUs.
Display comparison results, including correct matches, missing matches, and incorrect matches.
Print eBay URLs and associated IPNs for analysis.
