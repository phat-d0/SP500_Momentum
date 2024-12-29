import os
import time
from datetime import datetime, deltatime
import pandas as pd
from dotenv import load_dotenv
import csv
from alpaca_trade_api.rest import REST

load_dotenv()

# 1. Initialize Alpaca API Client
APCA_API_KEY = os.getenv("APCA_API_KEY")
APCA_SECRET = os.getenv("APCA_SECRET")
APCA_API_BASE_URL = "https://paper-api.alpaca.markets"
alpaca = REST(APCA_API_KEY, APCA_SECRET, APCA_API_BASE_URL)


# 2. Fetch Historical Data
def fetch_alpaca_historical_data(symbols, start_date, end_date, timeframe='1Min'):
    """
    Fetch historical data for a list of symbols from Alpaca.
    Args:
        symbols (list): List of stock symbols.
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        timeframe (str): Timeframe for bars (e.g., '1Min').
    Returns:
        dict: A dictionary of DataFrames for each symbol.
    """
    historical_data = {}
    market_open = time(9, 30)  # 9:30 AM
    market_close = time(16, 0)  # 4:00 PM

    for symbol in symbols:
        try:
            bars = alpaca.get_bars(symbol, timeframe, start=start_date, end=end_date).df
            bars.index = pd.to_datetime(bars.index)  # Ensure datetime format
            # Filter for regular market hours
            bars = bars[(bars.index.time >= market_open) & (bars.index.time <= market_close)]
            historical_data[symbol] = bars[['open', 'close', 'high', 'low', 'volume']]
            time.sleep(0.25)  # Avoid hitting API rate limits
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
    return historical_data

# 3. Strategy Logic
def calculate_percentage_change(previous_close, today_open):
    return (today_open - previous_close) / previous_close * 100

def get_top_and_bottom_movers(historical_data, date):
    movers = []
    for symbol, df in historical_data.items():
        try:
            prev_close = df.loc[date, 'close']
            today_open = df.loc[date, 'open']
            change = calculate_percentage_change(prev_close, today_open)
            movers.append((symbol, change))
        except KeyError:
            continue
    movers.sort(key=lambda x: x[1], reverse=True)
    top_10 = movers[:10]
    bottom_10 = movers[-10:]
    return top_10, bottom_10


# 4. Simulate Trades (Updated with Closing Trades)
def place_trades(portfolio, movers, allocation, prices, trade_type):
    """
    Simulate placing trades and adds them to the portfolio.
    """
    for symbol, _ in movers:
        if symbol not in prices:
            continue
        price = prices[symbol]
        quantity = allocation // price
        portfolio.append({
            'symbol': symbol,
            'quantity': quantity if trade_type == 'buy' else -quantity,
            'price': price,
            'trade_type': trade_type
        })


def close_positions_and_log(portfolio, prices, date, trade_log_file):
    """
    Simulate closing positions and log the trades.
    """
    pnl = 0
    closing_trades = []

    for position in portfolio:
        close_price = prices.get(position['symbol'], 0)
        pnl += (close_price - position['price']) * position['quantity']
        
        # Log closing trades
        closing_trades.append({
            'symbol': position['symbol'],
            'quantity': -position['quantity'],  # Reverse the position to close
            'price': close_price,
            'trade_type': 'close'
        })

    # Log all closing trades to CSV
    log_trades_to_csv(date, closing_trades, trade_log_file)
    return pnl


# 6. Backtesting Function (Updated with Closing Trades)
def backtest(historical_data, cash=100000, allocation_pct=1, trade_log_file="trades_log.csv"):
    portfolio = []
    pnl_history = []
    cash_balance = cash

    # Clear the log file at the start of the backtest
    if os.path.exists(trade_log_file):
        os.remove(trade_log_file)

    dates = sorted(list(historical_data[list(historical_data.keys())[0]].index))
    for date in dates:
        portfolio.clear()  # Reset portfolio for each day

        # Get top and bottom movers
        top_movers, bottom_movers = get_top_and_bottom_movers(historical_data, date)

        # Allocate capital
        allocation = cash_balance * allocation_pct / 20

        # Simulate buying and shorting
        prices = {s: historical_data[s].loc[date, 'open'] for s in historical_data if date in historical_data[s].index}
        place_trades(portfolio, top_movers, allocation, prices, 'buy')
        place_trades(portfolio, bottom_movers, allocation, prices, 'sell')

        # Log opening trades
        log_trades_to_csv(date, portfolio, trade_log_file)

        # Close positions at the end of the day and log them
        prices_close = {s: historical_data[s].loc[date, 'close'] for s in historical_data if date in historical_data[s].index}
        pnl = close_positions_and_log(portfolio, prices_close, date, trade_log_file)
        pnl_history.append(pnl)
        cash_balance += pnl

    return pnl_history, cash_balance


# 5. Log Trades to CSV (Unchanged)
def log_trades_to_csv(date, portfolio, filename="trades_log.csv"):
    """
    Logs trades to a CSV file.

    Args:
        date (str): The trading date.
        portfolio (list): List of trade dictionaries containing symbol, quantity, price, and trade_type.
        filename (str): Name of the CSV file to save trades.
    """
    file_exists = os.path.isfile(filename)
    
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        
        # Write the header only if the file is new
        if not file_exists:
            writer.writerow(['Date', 'Symbol', 'Quantity', 'Price', 'Trade Type'])
        
        # Write each trade
        for trade in portfolio:
            writer.writerow([date, trade['symbol'], trade['quantity'], trade['price'], trade['trade_type']])


# 7. Analyze Results (Unchanged)
def analyze_performance(pnl_history, cash):
    cumulative_pnl = [sum(pnl_history[:i+1]) for i in range(len(pnl_history))]
    print(f"Final Portfolio Value: {cash + sum(cumulative_pnl)}")
    print(f"Total PnL: {sum(pnl_history)}")
    print(f"Sharpe Ratio: {calculate_sharpe_ratio(pnl_history)}")

    import matplotlib.pyplot as plt
    plt.plot(cumulative_pnl)
    plt.title('Cumulative PnL')
    plt.xlabel('Days')
    plt.ylabel('PnL ($)')
    plt.show()


# 8. Sharpe Ratio Calculation (Unchanged)
def calculate_sharpe_ratio(daily_returns, risk_free_rate=0.02):
    mean_return = pd.Series(daily_returns).mean()
    std_dev = pd.Series(daily_returns).std()
    return (mean_return - risk_free_rate / 252) / std_dev


# 9. Run Backtest (Unchanged)
if __name__ == "__main__":
    # Load symbols
    symbols_file = "S&P500_tickers.txt"  # File containing S&P 500 symbols
    with open(symbols_file, 'r') as f:
        symbols = [line.strip() for line in f.readlines()]

    # Fetch historical data
    start_date = "2023-01-01"
    end_date = datetime.today().strftime('%Y-%m-%d')
    historical_data = fetch_alpaca_historical_data(symbols, start_date, end_date)

    # Run backtest
    trade_log_file = "daily_trades.csv"
    pnl_history, final_cash = backtest(historical_data, trade_log_file=trade_log_file)

    # Analyze results
    analyze_performance(pnl_history, final_cash)
