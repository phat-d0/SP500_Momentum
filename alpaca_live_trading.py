import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import alpaca_trade_api as alpaca
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from trading_opportunities import get_top_and_bottom_movers  # Importing from trading_opportunities.py

# Load environment variables
load_dotenv()

# Alpaca API credentials
APCA_API_KEY = os.getenv("APCA_API_KEY")
APCA_SECRET = os.getenv("APCA_SECRET")
APCA_API_BASE_URL = "https://paper-api.alpaca.markets"

# Alpaca Client
trading_client = TradingClient(APCA_API_KEY, APCA_SECRET, paper=True)
api = alpaca.REST(APCA_API_KEY, APCA_SECRET, APCA_API_BASE_URL)

# Trading Functions
def get_cash_balance():
    """
    Retrieves the cash balance from the Alpaca account.
    """
    account = api.get_account()
    cash_balance = float(account.cash)
    print(f"Cash Balance: ${cash_balance}")
    return cash_balance

def place_order(symbol, qty, side):
    """
    Places an order using the Alpaca API.
    """
    try:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide(side),
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order)
        print(f"Order placed: {side} {qty} shares of {symbol}")
    except Exception as e:
        print(f"Failed to place order for {symbol}: {e}")

def calculate_allocation(cash_balance, percentage, num_positions):
    """
    Calculates the dollar amount to allocate per position.
    """
    return (cash_balance * percentage) / num_positions

def execute_strategy(top_movers, bottom_movers, allocation_per_position):
    """
    Executes the trading strategy by placing buy and short orders.
    """
    for symbol, change in top_movers:
        try:
            bar = api.get_latest_bar(symbol)
            current_price = bar.c
            shares = int(allocation_per_position // current_price)
            if shares > 0:
                place_order(symbol, shares, "buy")
        except Exception as e:
            print(f"Failed to buy {symbol}: {e}")

    for symbol, change in bottom_movers:
        try:
            bar = api.get_latest_bar(symbol)
            current_price = bar.c
            shares = int(allocation_per_position // current_price)
            if shares > 0:
                place_order(symbol, shares, "sell")
        except Exception as e:
            print(f"Failed to short {symbol}: {e}")

def close_all_positions():
    """
    Closes all open positions and calculates realized PnL based on closed trades.
    """
    try:
        print("Closing all open positions...")
        # Fetch all open positions
        positions = api.list_positions()

        if not positions:
            print("No open positions to close.")
            return

        # Iterate through positions, close each, and calculate realized PnL
        for position in positions:
            symbol = position.symbol
            qty = abs(int(position.qty))  # Ensure qty is positive for market orders
            side = "sell" if int(position.qty) > 0 else "buy"  # Determine sell for long, buy for short

            print(f"Closing position: {symbol}, Qty: {position.qty}")

            # Close the position
            try:
                place_order(symbol, qty, side)
            except Exception as e:
                print(f"Failed to close position for {symbol}: {e}")
                continue

            # Retrieve closed activities to calculate realized PnL
            time.sleep(2)  # Add a short delay to ensure trade completion
            activities = api.get_activities(activity_types="FILL")
            realized_pnl = 0
            for activity in activities:
                if activity.symbol == symbol:
                    realized_pnl += float(activity.cum_qty) * float(activity.price) * (-1 if side == "buy" else 1)

            print(f"Position: {symbol}, Realized PnL: ${realized_pnl:.2f}")

        print("All positions closed.")
    except Exception as e:
        print(f"Error while closing positions: {e}")


# Main Script
if __name__ == "__main__":
    # Step 1: Wait for market open (9:30 AM)
    market_open_time = datetime.combine(datetime.now().date(), datetime.strptime("09:30", "%H:%M").time())
    while True:
        current_time = datetime.now()
        if current_time >= market_open_time:
            print("Market is open! Starting strategy execution.")
            break
        else:
            time_until_open = market_open_time - current_time
            print(f"Waiting for market to open. Time until open: {time_until_open}")
            time.sleep(60)  # Check every minute

    # Step 2: Generate signals from trading_opportunities
    top_movers, bottom_movers = get_top_and_bottom_movers()

    # Step 3: Get cash balance and calculate allocation
    cash_balance = get_cash_balance()
    allocation_per_position = calculate_allocation(cash_balance, 1.0, 20)

    # Step 4: Execute strategy
    execute_strategy(top_movers, bottom_movers, allocation_per_position)

    # Step 5: Monitor time and close positions 15 minutes before market close
    market_close_time = datetime.combine(datetime.now().date(), datetime.strptime("16:00", "%H:%M").time())
    while True:
        current_time = datetime.now()
        time_until_close = market_close_time - current_time
        if time_until_close <= timedelta(minutes=15):
            print("15 minutes before market close. Closing all positions.")
            close_all_positions()
            break
        else:
            print(f"Waiting for market close. Time until close: {time_until_close}")
            time.sleep(60)  # Check every minute
