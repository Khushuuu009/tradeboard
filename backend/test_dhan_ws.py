from dhanhq import marketfeed
import os, asyncio
from dotenv import load_dotenv
load_dotenv()

client_id    = os.getenv('DHAN_CLIENT_ID')
access_token = os.getenv('DHAN_ACCESS_TOKEN')

instruments = [(marketfeed.IDX, "13", marketfeed.Quote)]

async def main():
    print("Connecting with v2...")
    feed = marketfeed.DhanFeed(
        client_id    = client_id,
        access_token = access_token,
        instruments  = instruments,
        version      = 'v2'
    )

    await feed.connect()
    print("Connected! Waiting for ticks...")

    for i in range(5):
        # Use the internal async method directly
        data = await feed.get_instrument_data()
        print(f"Tick {i+1}: {data}")

    await feed.disconnect()
    print("Done!")

asyncio.run(main())