import requests
import pandas as pd
from io import StringIO

url = 'https://images.dhan.co/api-data/api-scrip-master.csv'
r = requests.get(url, timeout=30)
df = pd.read_csv(StringIO(r.text), low_memory=False)

print('Total rows:', len(df))
print('Columns:', list(df.columns))
print()

# Filter NIFTY OPTIDX on NSE
nifty = df[
    (df['SM_SYMBOL_NAME'].astype(str).str.upper() == 'NIFTY') &
    (df['SEM_EXCH_INSTRUMENT_TYPE'].astype(str) == 'OPTIDX')
]

print('NIFTY OPTIDX rows:', len(nifty))
print()
print(nifty[['SEM_SMST_SECURITY_ID','SEM_TRADING_SYMBOL','SEM_EXPIRY_DATE','SEM_STRIKE_PRICE','SEM_OPTION_TYPE','SEM_SEGMENT']].head(20).to_string())