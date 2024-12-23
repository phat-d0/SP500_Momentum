import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import urllib.parse

# Load environment variables
load_dotenv()

# Alpaca API credentials
APCA_API_KEY = os.getenv("APCA_API_KEY")
APCA_SECRET = os.getenv("APCA_SECRET")
APCA_API_BASE_URL = "https://data.alpaca.markets/v2"

# Load S&P 500 symbols from the text file
def load_sp500_symbols(file_path):
    """
    Reads S&P 500 symbols from a text file.
    Each symbol should be on a new line.
    """
    try:
        with open(file_path, 'r') as file:
            symbols = [line.strip() for line in file if line.strip()]
        return symbols
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return []

SP500_SYMBOLS = load_sp500_symbols('S&P500_tickers.txt')

def get_previous_trading_day():
    """
    Returns the previous trading day's date in 'YYYY-MM-DD' format.
    """
    today = datetime.today()
    offset = max(1, (today.weekday() + 6) % 7 - 3)
    delta = timedelta(offset)
    previous_trading_day = today - delta
    return previous_trading_day.strftime('%Y-%m-%d')

def get_daily_bar(symbol, start_date, end_date):
    """
    Fetches the daily bar for a given symbol between start_date and end_date.
    Returns the previous day's close and the current day's open.
    """
    url = f"{APCA_API_BASE_URL}/stocks/{urllib.parse.quote(symbol)}/bars"
    headers = {
        "APCA-API-KEY-ID": APCA_API_KEY,
        "APCA-API-SECRET-KEY": APCA_SECRET,
    }
    params = {
        "start": start_date,
        "end": end_date,
        "timeframe": "1Day",
        "adjustment": "split"
    }

    try:
        # Log the API request
        #print(f"Fetching bars for {symbol}: {start_date} to {end_date}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        bars = response.json().get('bars', None)

        # Debug the API response
        if bars is None:
            print(f"No bars returned for {symbol}. Full response: {response.json()}")
            return None, None

        # Log the retrieved bars
        #print(f"Bars for {symbol}: {bars}")

        if len(bars) >= 2:  # Ensure we have at least 2 bars (yesterday and today)
            previous_close = bars[-2]['c']  # Close of the previous day
            today_open = bars[-1]['o']      # Open of the current day
            print(f"{symbol} - Previous Close: {previous_close}, Today Open: {today_open}")
            return previous_close, today_open
        else:
            print(f"Not enough bars for {symbol}. Received: {bars}")
            return None, None

    except requests.exceptions.RequestException as e:
        # Catch any API-related errors
        print(f"Error fetching data for {symbol}: {e}")
        return None, None

def calculate_percentage_change(previous_close, today_open):
    """
    Calculates the percentage change from the previous day's close to today's open.
    """
    if previous_close == 0:
        return 0
    return ((today_open - previous_close) / previous_close) * 100

def get_top_and_bottom_movers():
    """
    Identifies the top 10 gainers and losers in the S&P 500 for the day.
    """
    previous_trading_day = get_previous_trading_day()
    today = datetime.today().strftime('%Y-%m-%d')

    # Debug prints for trading days
    print(f"Today's date: {today}")
    print(f"Previous trading day: {previous_trading_day}")

    movers = []

    for symbol in SP500_SYMBOLS:
        previous_close, today_open = get_daily_bar(symbol, previous_trading_day, today)
        if previous_close is not None and today_open is not None:
            percent_change = calculate_percentage_change(previous_close, today_open)
            movers.append((symbol, percent_change))

    # Sort movers by percentage change
    movers.sort(key=lambda x: x[1], reverse=True)

    # Top 10 gainers
    top_10_gainers = movers[:10]

    # Bottom 10 losers
    bottom_10_losers = movers[-10:]

    return top_10_gainers, bottom_10_losers

if __name__ == "__main__":
    if not SP500_SYMBOLS:
        print("No S&P 500 symbols loaded. Ensure 'S&P500_tickers.txt' exists and is populated.")
    else:
        top_gainers, bottom_losers = get_top_and_bottom_movers()
        print("\nTop 10 Gainers:")
        for symbol, change in top_gainers:
            print(f"{symbol}: {change:.2f}%")
        print("\nBottom 10 Losers:")
        for symbol, change in bottom_losers:
            print(f"{symbol}: {change:.2f}%")
