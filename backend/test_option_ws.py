from dhanhq import dhanhq, marketfeed
import os, asyncio
from dotenv import load_dotenv
load_dotenv()

dhan  = dhanhq(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))
chain = dhan.option_chain(under_security_id=13, under_exchange_segment='IDX_I', expiry='2026-03-17')

data    = chain['data']['data']
spot    = data['last_price']
oc      = data['oc']
atm     = round(spot / 50) * 50
atm_key = f'{float(atm):.6f}'

ce_id = oc[atm_key]['ce']['security_id']
pe_id = oc[atm_key]['pe']['security_id']

print(f'Spot: {spot}')
print(f'ATM: {atm}')
print(f'CE security_id: {ce_id}')
print(f'PE security_id: {pe_id}')

# Subscribe to CE and PE via WebSocket
async def main():
    instruments = [
        (marketfeed.IDX,     "13",       marketfeed.Quote),
        (marketfeed.NSE_FNO, str(ce_id), marketfeed.Quote),
        (marketfeed.NSE_FNO, str(pe_id), marketfeed.Quote),
    ]
    feed = marketfeed.DhanFeed(
        client_id    = os.getenv('DHAN_CLIENT_ID'),
        access_token = os.getenv('DHAN_ACCESS_TOKEN'),
        instruments  = instruments,
        version      = 'v2'
    )
    await feed.connect()
    print('Connected! Getting ticks...')
    for i in range(10):
        tick = await feed.get_instrument_data()
        sec  = tick.get('security_id')
        ltp  = tick.get('LTP')
        name = 'NIFTY' if str(sec) == '13' else ('CE' if str(sec) == str(ce_id) else 'PE')
        print(f'{name} ({sec}): LTP={ltp}')
    await feed.disconnect()

asyncio.run(main())