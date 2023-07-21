import argparse
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from aiofiles import open as aioopen
from aiopath import AsyncPath
import websockets


async def fetch_exchange_rates(session, date):
    url = f"https://api.privatbank.ua/p24api/exchange_rates?json&date={date}"
    async with session.get(url) as response:
        return await response.json()


async def get_exchange_rates(start_date, days):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(days):
            date = (start_date - timedelta(days=i)).strftime("%d.%m.%Y")
            task = asyncio.create_task(fetch_exchange_rates(session, date))
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results


async def write_to_log(data):
    async with aioopen("log.txt", mode="a") as file:
        await file.write(data + "\n")


async def handle_command(command, websocket, args):
    if command.startswith("exchange"):
        parts = command.split()
        if len(parts) > 1:
            days = int(parts[1])
            start_date = datetime.now().date()
            exchange_rates = await get_exchange_rates(start_date, days)

            result = []
            for i, rates in enumerate(exchange_rates):
                date = (start_date - timedelta(days=i)).strftime("%d.%m.%Y")
                currencies = {currency: {} for currency in args.currencies}
                for rate in rates["exchangeRate"]:
                    if rate["currency"] in args.currencies:
                        currencies[rate["currency"]]["sale"] = rate["saleRateNB"]
                        currencies[rate["currency"]]["purchase"] = rate["purchaseRateNB"]

                result.append({date: currencies})

            response = json.dumps(result, indent=2)
            await websocket.send(response)
            await write_to_log(f"Exchange rates fetched for {days} days")


async def chat_server(websocket, path):
    async for message in websocket:
        await handle_command(message, websocket)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("days", type=int, help="Number of days to fetch exchange rates")
    parser.add_argument("-c", "--currencies", nargs="+", default=["EUR", "USD"],
                        help="Additional currencies to fetch exchange rates")
    args = parser.parse_args()

    start_date = datetime.now().date()
    exchange_rates = await get_exchange_rates(start_date, args.days)

    result = []
    for i, rates in enumerate(exchange_rates):
        date = (start_date - timedelta(days=i)).strftime("%d.%m.%Y")
        currencies = {currency: {} for currency in args.currencies}
        for rate in rates["exchangeRate"]:
            if rate["currency"] in args.currencies:
                currencies[rate["currency"]]["sale"] = rate["saleRateNB"]
                currencies[rate["currency"]]["purchase"] = rate["purchaseRateNB"]

        result.append({date: currencies})

    print(json.dumps(result, indent=2))
    await write_to_log(f"Exchange rates fetched for {args.days} days and currencies: {', '.join(args.currencies)}")

    # Создание WebSocket-сервера для чата
    start_server = websockets.serve(lambda ws, path: handle_command(ws, path, args), "localhost", 8765)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    asyncio.run(main())
