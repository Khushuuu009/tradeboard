import requests

BASE_URL = 'https://straddle-chart.financedeft.com/history'

# For 2026-03-09, two expiries available: 2026-03-10 and 2026-03-17
# Fetch both and compare closing straddle

def get_closing(date, expiry):
    url  = f'{BASE_URL}/equity/NIFTY/{date}/{expiry}.json'
    r    = requests.get(url)
    if r.status_code != 200:
        return None
    pl   = r.json().get('price_list', [])
    if not pl:
        return None
    last = pl[-1]
    return {
        'expiry':   expiry,
        'strike':   last['straddle_strike'],
        'ce':       last['ce_price'],
        'pe':       last['pe_price'],
        'total':    round(last['ce_price'] + last['pe_price'], 2),
        'spot':     last['spot'],
    }

date     = '2026-03-09'
expiry1  = get_closing(date, '2026-03-10')
expiry2  = get_closing(date, '2026-03-17')

print(f'Date: {date}')
print(f'Expiry 2026-03-10: {expiry1}')
print(f'Expiry 2026-03-17: {expiry2}')
print()

# Pick lowest
both   = [e for e in [expiry1, expiry2] if e]
lowest = min(both, key=lambda x: x['total'])
print(f'Lowest straddle: {lowest}')