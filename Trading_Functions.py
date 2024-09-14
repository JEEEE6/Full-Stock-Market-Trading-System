import os
import logging



#time headaches
import pandas_market_calendars as mcal
from datetime import datetime, timedelta
import pytz



import pandas as pd
import numpy as np


# Setup logging
logging.basicConfig(filename='__Trading_Functions.log', level=logging.INFO, filemode='a')

BACKTEST_PARQUET_FILE = '_Buy_Signals.parquet'
LIVE_PARQUET_FILE = '_Live_trades.parquet'

COLUMNS = [
        'Symbol', 'LastBuySignalDate', 'LastBuySignalPrice', 'IsCurrentlyBought', 
        'ConsecutiveLosses', 'LastTradedDate', 'UpProbability', 'LastSellPrice'
    ]




def get_parquet_file(is_live=False):
    return LIVE_PARQUET_FILE if is_live else BACKTEST_PARQUET_FILE




def initialize_parquet(is_live=False):
    df = pd.DataFrame(columns=[
        'Symbol', 'LastBuySignalDate', 'LastBuySignalPrice', 'IsCurrentlyBought', 
        'ConsecutiveLosses', 'LastTradedDate', 'UpProbability', 'LastSellPrice'
    ])
    df.to_parquet(get_parquet_file(is_live), index=False)




def read_trading_data(is_live=False):
    file = get_parquet_file(is_live)
    if not os.path.exists(file):
        initialize_parquet(is_live)
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_parquet(file)
    
    # Convert date columns to datetime
    date_columns = ['LastBuySignalDate', 'LastTradedDate']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    
    return df




 

def write_trading_data(df, is_live=False):
    # Convert date columns to datetime
    date_columns = ['LastBuySignalDate', 'LastTradedDate']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date  # Convert to date

    # Replace NaT with None for Parquet compatibility
    for col in df.select_dtypes(include=['datetime64', 'object']).columns:
        df[col] = df[col].where(pd.notnull(df[col]), None)
    
    df.to_parquet(get_parquet_file(is_live), index=False)




def update_buy_signal(symbol, date, price, up_probability, is_live=False):
    """Update or add a buy signal for a symbol."""
    up_probability = round(up_probability, 4)
    price = round(price, 4)

    df = read_trading_data(is_live)
    new_data = pd.DataFrame({
        'Symbol': [symbol],
        'LastBuySignalDate': [pd.Timestamp(date)],  # Convert date to Timestamp
        'LastBuySignalPrice': [price],
        'IsCurrentlyBought': [False],
        'ConsecutiveLosses': [0],
        'LastTradedDate': [None],
        'UpProbability': [up_probability]
    })
    df = pd.concat([df[df['Symbol'] != symbol], new_data], ignore_index=True)
    
    # Ensure all date columns are converted to datetime
    date_columns = ['LastBuySignalDate', 'LastTradedDate']
    for col in date_columns:
        df[col] = pd.to_datetime(df[col])
    
    write_trading_data(df, is_live)





def mark_position_as_bought(symbol, position_size, is_live=False):
    """Mark a symbol as currently bought with its position size."""
    df = read_trading_data(is_live)
    df.loc[df['Symbol'] == symbol, 'IsCurrentlyBought'] = True
    df.loc[df['Symbol'] == symbol, 'PositionSize'] = position_size
    write_trading_data(df, is_live)






def update_trade_data(symbol, trade_type, price, date, position_size, up_probability=None, is_live=False):
    """
    Update the trading data for both buy and sell operations.
    
    :param symbol: The stock symbol
    :param trade_type: 'buy' or 'sell'
    :param price: The price at which the trade occurred
    :param date: The date of the trade
    :param position_size: The size of the position (positive for buy, negative for sell)
    :param up_probability: The up probability for buy signals (optional)
    :param is_live: Whether this is live trading or not
    """
    df = read_trading_data(is_live)
    
    if symbol not in df['Symbol'].values:
        new_row = {
            'Symbol': symbol,
            'LastBuySignalDate': None,
            'LastBuySignalPrice': None,
            'IsCurrentlyBought': False,
            'ConsecutiveLosses': 0,
            'LastTradedDate': None,
            'UpProbability': None,
            'LastSellPrice': None,
            'PositionSize': 0
        }
        df = df.append(new_row, ignore_index=True)
    
    if trade_type == 'buy':
        df.loc[df['Symbol'] == symbol, 'LastBuySignalDate'] = pd.Timestamp(date)
        df.loc[df['Symbol'] == symbol, 'LastBuySignalPrice'] = price
        df.loc[df['Symbol'] == symbol, 'IsCurrentlyBought'] = True
        df.loc[df['Symbol'] == symbol, 'PositionSize'] = position_size
        df.loc[df['Symbol'] == symbol, 'ConsecutiveLosses'] = 0
        if up_probability is not None:
            df.loc[df['Symbol'] == symbol, 'UpProbability'] = up_probability
    elif trade_type == 'sell':
        df.loc[df['Symbol'] == symbol, 'LastTradedDate'] = pd.Timestamp(date)
        df.loc[df['Symbol'] == symbol, 'LastSellPrice'] = price
        df.loc[df['Symbol'] == symbol, 'IsCurrentlyBought'] = False
        df.loc[df['Symbol'] == symbol, 'PositionSize'] = 0
    
    df.loc[df['Symbol'] == symbol, 'LastTradedDate'] = pd.Timestamp(date)
    
    write_trading_data(df, is_live)
    
    logging.info(f"Updated trade data for {symbol}: Trade Type={trade_type}, Price={price}, Date={date}, Position Size={position_size}")
    
    # Verify the update
    updated_df = read_trading_data(is_live)
    updated_row = updated_df[updated_df['Symbol'] == symbol].iloc[0]
    logging.info(f"Verified data for {symbol}: IsCurrentlyBought={updated_row['IsCurrentlyBought']}, PositionSize={updated_row['PositionSize']}, BuyDate={updated_row['LastBuySignalDate']}")









def update_trade_result(symbol, is_loss, exit_price=None, exit_date=None, is_live=False):
    df = read_trading_data(is_live)
    if symbol in df['Symbol'].values:
        if is_loss:
            df.loc[df['Symbol'] == symbol, 'ConsecutiveLosses'] += 1
        else:
            df.loc[df['Symbol'] == symbol, 'ConsecutiveLosses'] = 0
        
        if is_live:
            if exit_price is None or exit_date is None:
                raise ValueError("exit_price and exit_date are required for live trading")
            df.loc[df['Symbol'] == symbol, 'LastTradedDate'] = pd.Timestamp(exit_date)
            df.loc[df['Symbol'] == symbol, 'LastSellPrice'] = exit_price
        else:
            df.loc[df['Symbol'] == symbol, 'LastTradedDate'] = pd.Timestamp(exit_date or datetime.now().date())
            if exit_price is not None:
                df.loc[df['Symbol'] == symbol, 'LastSellPrice'] = exit_price
        
        df.loc[df['Symbol'] == symbol, 'IsCurrentlyBought'] = False
        
        # Convert all date columns to pandas Timestamp
        date_columns = ['LastBuySignalDate', 'LastTradedDate']
        for col in date_columns:
            df[col] = pd.to_datetime(df[col])
        
        write_trading_data(df, is_live)





def get_buy_signals(is_live=False):
    try:
        df = read_trading_data(is_live)
        current_date = datetime.now(pytz.timezone('US/Eastern')).date()
        previous_trading_day = get_previous_trading_day(current_date)
        
        df['LastBuySignalDate'] = pd.to_datetime(df['LastBuySignalDate']).dt.date
        
        signals = df[
            (df['IsCurrentlyBought'] == False) & 
            (df['LastBuySignalDate'] == previous_trading_day)
        ].to_dict('records')
        
        if not signals:
            logging.info(f"No buy signals found for the previous trading day ({previous_trading_day})")
        else:
            logging.info(f"Found {len(signals)} buy signals for {previous_trading_day}")
        
        return signals
    except Exception as e:
        logging.error(f"Error in get_buy_signals: {e}")
        return []





def get_previous_trading_day(current_date):
    """Get the previous trading day using pandas_market_calendars."""
    nyse = mcal.get_calendar('NYSE')
    
    # Convert current_date to datetime if it's not already
    if not isinstance(current_date, datetime):
        current_date = pd.Timestamp(current_date)
    
    # Get the schedule for the past 10 days (arbitrary, but should be enough)
    end_date = current_date.date()
    start_date = end_date - timedelta(days=10)
    schedule = nyse.schedule(start_date=start_date, end_date=end_date)
    
    # Find the last trading day before or on the current date
    valid_days = schedule[schedule.index.date <= end_date]
    if valid_days.empty:
        raise ValueError(f"No trading days found in the 10 days before {end_date}")
    
    return valid_days.index[-1].date()


def is_market_open():
    """Check if the U.S. stock market is currently open using pandas_market_calendars."""
    nyse = mcal.get_calendar('NYSE')
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    # Get today's schedule
    schedule = nyse.schedule(start_date=now.date(), end_date=now.date())
    
    if schedule.empty:
        return False  # Market is closed (weekend or holiday)
    
    market_open = schedule.iloc[0]['market_open'].tz_convert(eastern)
    market_close = schedule.iloc[0]['market_close'].tz_convert(eastern)
    
    return market_open <= now <= market_close



def get_open_positions(is_live=False):
    """Get all currently bought positions."""
    df = read_trading_data(is_live)
    return df[df['IsCurrentlyBought'] == True]['Symbol'].tolist()




def calculate_position_size(total_value, cash, reserve_percent, max_positions, current_price):
    """Calculate the position size for a new trade."""
    workable_capital = total_value * (1 - reserve_percent)
    capital_per_position = workable_capital / max_positions
    
    if cash < capital_per_position or cash < (total_value * reserve_percent):
        return 0
    
    return int(capital_per_position / current_price) - 1




def should_sell(current_price, entry_price, entry_date, current_date, 
               stop_loss_percent=5.0, take_profit_percent=100.0, 
               max_hold_days=9, min_daily_return=0.25, verbose=False):
    """Determine if a position should be sold based on various criteria."""
    days_held = (current_date - entry_date).days
    profit_percent = (current_price - entry_price) / entry_price * 100

    stop_loss = current_price <= entry_price * (1 - stop_loss_percent / 100)
    take_profit = current_price >= entry_price * (1 + take_profit_percent / 100)
    max_hold = days_held > max_hold_days
    low_return = days_held > 3 and (profit_percent / days_held) < min_daily_return

    if verbose:
        reasons = []
        if stop_loss:
            reasons.append("Stop Loss")
        if take_profit:
            reasons.append("Take Profit")
        if max_hold:
            reasons.append("Max Hold")
        if low_return:
            reasons.append("Low Return")
        logging.info(f"Sell Conditions Met: {', '.join(reasons) if reasons else 'None'}")

    return stop_loss or take_profit or max_hold or low_return






def prioritize_buy_signals(buy_signals, correlation_data):
    """Prioritize buy signals based on group correlations and up probability."""
    merged_data = pd.merge(buy_signals, correlation_data, on='Symbol', how='left')
    group_allocations = merged_data.groupby('Cluster')['IsCurrentlyBought'].sum() / len(merged_data)
    merged_data['GroupAllocation'] = merged_data['Cluster'].map(group_allocations)
    return merged_data.sort_values(['GroupAllocation', 'UpProbability'], ascending=[True, False])

def get_cooldown_end(consecutive_losses):
    """Get the cooldown end date based on consecutive losses."""
    cooldown_days = {1: 7, 2: 28, 3: 90, 4: 282}
    days = cooldown_days.get(consecutive_losses, 282 if consecutive_losses >= 4 else 0)
    return datetime.now().date() + timedelta(days=days)

def is_in_cooldown(trading_data, symbol, current_date):
    """Check if a symbol is in cooldown period."""
    if symbol not in trading_data.index:
        return False
    
    consecutive_losses = trading_data.loc[symbol, 'ConsecutiveLosses']
    last_traded_date = trading_data.loc[symbol, 'LastTradedDate']
    
    if pd.isnull(last_traded_date):
        return False
    
    cooldown_end = get_cooldown_end(consecutive_losses)
    return current_date <= cooldown_end

def check_group_correlation(symbol, current_positions, correlation_data, max_positions_per_cluster=2):
    """Check if adding a new position would violate group correlation limits."""
    if symbol not in correlation_data.index:
        return True  # If we don't have correlation data, assume it's safe to trade

    symbol_cluster = correlation_data.loc[symbol, 'Cluster']
    current_clusters = [correlation_data.loc[pos, 'Cluster'] for pos in current_positions if pos in correlation_data.index]
    
    # Count how many positions are already in the same cluster
    cluster_count = sum(1 for cluster in current_clusters if cluster == symbol_cluster)
    
    return cluster_count < max_positions_per_cluster

def get_consecutive_losses(symbol, is_live=False):
    """Get the number of consecutive losses for a symbol."""
    df = read_trading_data(is_live)
    if symbol in df['Symbol'].values:
        return df.loc[df['Symbol'] == symbol, 'ConsecutiveLosses'].iloc[0]
    return 0

def get_days_since_last_trade(symbol, is_live=False):
    """Get the number of days since the last trade for a symbol."""
    df = read_trading_data(is_live)
    if symbol in df['Symbol'].values and pd.notnull(df.loc[df['Symbol'] == symbol, 'LastTradedDate'].iloc[0]):
        last_trade_date = df.loc[df['Symbol'] == symbol, 'LastTradedDate'].iloc[0]
        return (datetime.now() - last_trade_date).days
    return None




def colorize_output(value, label, good_threshold, bad_threshold, lower_is_better=False, reverse=False):
    def get_color_code(normalized_value):
        # Define color steps with slightly toned down brightness for extremes
        colors = [
            (0, 235, 0),    # Slightly toned down Bright Green
            (0, 180, 0),    # Normal Green
            (220, 220, 0),  # Yellow
            (220, 140, 0),  # Orange
            (220, 0, 0),    # Red
            (240, 0, 0)     # Slightly toned down Bright Red
        ]
        
        # Calculate which color pair to interpolate between
        index = min(int(normalized_value * (len(colors) - 1)), len(colors) - 2)
        
        # Interpolate between the two colors
        t = (normalized_value * (len(colors) - 1)) - index
        r = int(colors[index][0] * (1-t) + colors[index+1][0] * t)
        g = int(colors[index][1] * (1-t) + colors[index+1][1] * t)
        b = int(colors[index][2] * (1-t) + colors[index+1][2] * t)
        
        return f"\033[38;2;{r};{g};{b}m"

    # Adjust thresholds and normalization for reverse and lower_is_better scenarios
    if reverse:
        good_threshold, bad_threshold = bad_threshold, good_threshold

    if lower_is_better:
        if value <= good_threshold:
            normalized_value = 0  # Best value (Green)
        elif value >= bad_threshold:
            normalized_value = 1  # Worst value (Red)
        else:
            normalized_value = (value - good_threshold) / (bad_threshold - good_threshold)
    else:
        if value >= good_threshold:
            normalized_value = 0  # Best value (Green)
        elif value <= bad_threshold:
            normalized_value = 1  # Worst value (Red)
        else:
            normalized_value = (good_threshold - value) / (good_threshold - bad_threshold)

    color_code = get_color_code(normalized_value)
    return f"{label:<30}{color_code}{value:.2f}\033[0m"








# Initialize both Parquet files if they don't exist
if not os.path.exists(BACKTEST_PARQUET_FILE):
    initialize_parquet(False)
if not os.path.exists(LIVE_PARQUET_FILE):
    initialize_parquet(True)
