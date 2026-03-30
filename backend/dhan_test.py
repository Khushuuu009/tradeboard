from dhanhq import dhanhq
import os, inspect
from dotenv import load_dotenv
load_dotenv()

dhan = dhanhq(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))

# Check relevant methods
methods = [m for m in dir(dhan) if any(x in m.lower() for x in ['roll', 'option', 'hist', 'expir'])]
print('Relevant methods:', methods)

# Check signatures
print()
print('historical_daily_data:', inspect.signature(dhan.historical_daily_data))
print('intraday_minute_data:', inspect.signature(dhan.intraday_minute_data))