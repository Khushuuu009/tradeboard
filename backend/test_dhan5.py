import requests
import pandas as pd
from io import StringIO

url = 'https://images.dhan.co/api-data/api-scrip-master.csv'
r = requests.get(url, timeout=30)
df = pd.read_csv(StringIO(r.text), low_memory=False)

# Check OPTIDX rows
optidx = df[df['SEM_EXCH_INSTRUMENT_TYPE'].astype(str) == 'OPTIDX']
print('Total OPTIDX rows:', len(optidx))
print('Unique SM_SYMBOL_NAME in OPTIDX:', optidx['SM_SYMBOL_NAME'].unique()[:20])
print('Unique SEM_SEGMENT in OPTIDX:', optidx['SEM_SEGMENT'].unique())
print()

# Try searching for NIFTY in trading symbol
nifty_trading = df[df['SEM_TRADING_SYMBOL'].astype(str).str.contains('NIFTY', na=False)]
print('NIFTY in trading symbol:', len(nifty_trading))
print('Instrument types:', nifty_trading['SEM_EXCH_INSTRUMENT_TYPE'].unique())
print()
print(nifty_trading[nifty_trading['SEM_EXCH_INSTRUMENT_TYPE'] == 'OPTIDX'][
    ['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_EXPIRY_DATE','SEM_STRIKE_PRICE','SEM_OPTION_TYPE']
].head(10).to_string())