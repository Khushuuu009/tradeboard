import requests
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv()

# Dhan publishes a full instrument master file
# Let's try downloading it directly
urls_to_try = [
    'https://images.dhan.co/api-data/api-scrip-master.csv',
    'https://api.dhan.co/v2/instruments',
    'https://images.dhan.co/api-data/NSE_FO.csv',
]

for url in urls_to_try:
    try:
        r = requests.get(url, timeout=10)
        print(f'URL: {url}')
        print(f'Status: {r.status_code}')
        if r.status_code == 200:
            print(f'Content preview: {r.text[:300]}')
        print()
    except Exception as e:
        print(f'URL: {url} ERROR: {e}')
        print()