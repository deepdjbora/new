import threading
import time
import pandas as pd

# New dictionary to store entry prices
entry_prices = {}

def realtime_exit_checker(
    current_positions,
    entry_instruments,
    profit_target,
    stop_loss,
    extra_feedJson
):
    def check_exits():
        while True:
            for token, position in current_positions.items():
                if position is None:
                    continue

                instrument_info = entry_instruments.get(token, {})
                op_token = instrument_info.get('op_token')
                op_symbol = instrument_info.get('op_symbol')

                if op_token is None or op_symbol is None:
                    continue

                current_price = get_latest_price(op_token)
                if current_price is None:
                    continue

                # Get the entry price from our new dictionary
                entry_price = entry_prices.get(op_symbol)
                if entry_price is None:
                    continue

                if position == 'long':
                    profit = current_price - entry_price
                    if profit >= profit_target or profit <= -stop_loss:
                        execute_exit(token, op_token, op_symbol, current_price, "REALTIME_LONG_EXIT")
                elif position == 'short':
                    profit = entry_price - current_price
                    if profit >= profit_target or profit <= -stop_loss:
                        execute_exit(token, op_token, op_symbol, current_price, "REALTIME_SHORT_EXIT")

            time.sleep(0.1)  # Check every 100ms, adjust as needed

    def execute_exit(token, op_token, op_symbol, price, exit_type):
        timestamp = pd.Timestamp.now()
        log_trade(timestamp, op_symbol, exit_type, price, timestamp)
        print(f"{exit_type} for {op_symbol} at {timestamp} price: {price}")
        current_positions[token] = None
        entry_instruments.pop(token, None)
        entry_prices.pop(op_symbol, None)  # Remove the entry price when exiting

    exit_thread = threading.Thread(target=check_exits, daemon=True)
    exit_thread.start()

# Add this to your main code, after initializing necessary variables
profit_target = 10  # Set your desired profit target
stop_loss = 5  # Set your desired stop loss
realtime_exit_checker(current_positions, entry_instruments, profit_target, stop_loss, extra_feedJson)

# Modify your process_token_data function to include entry price logging
def process_token_data(token):
    # ... (your existing code)

    if action_taken or current_positions.get(token) is None:
        if (EMA_short_latest > EMA_long_latest) and (EMA_short_previous <= EMA_long_previous) and df['is_bullish'].iloc[-1]:
            # ... (your existing long entry code)
            if price is not None:
                action_time = pd.Timestamp.now()
                log_trade(timestamp, state.ce_trading_symbol, "LONG ENTRY", price, action_time)
                print(f"Long Entry Signal for {state.ce_trading_symbol} at {timestamp} at {pd.Timestamp.now()} EMA_short_latest: {EMA_short_latest} EMA_long_latest: {EMA_long_latest} EMA_short_previous :{ EMA_short_previous} EMA_long_previous: {EMA_long_previous}")
                current_positions[token] = 'long'
                entry_prices[state.ce_trading_symbol] = price  # Store the entry price

        elif (EMA_short_latest < EMA_long_latest) and (EMA_short_previous >= EMA_long_previous) and df['is_bearish'].iloc[-1]:
            # ... (your existing short entry code)
            if price is not None:
                action_time = pd.Timestamp.now()
                log_trade(timestamp, state.pe_trading_symbol, "SHORT ENTRY", price, action_time)
                print(f"Short Entry Signal for {state.pe_trading_symbol} at {timestamp} at {pd.Timestamp.now()} EMA_short_latest: {EMA_short_latest} EMA_long_latest: {EMA_long_latest} EMA_short_previous :{ EMA_short_previous} EMA_long_previous: {EMA_long_previous}")
                current_positions[token] = 'short'
                entry_prices[state.pe_trading_symbol] = price  # Store the entry price

    # ... (rest of your existing code)