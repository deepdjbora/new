from collections import defaultdict

# Store potential entry signals and their timestamps
delayed_entries = defaultdict(lambda: {'timestamp': None, 'direction': None, 'price': None})

def delayed_entry_logic(token, df, current_positions, state, delayed_entries, delay_minutes=1):
    """
    Handles the delayed entry logic based on Chandelier Exit signals and retracement conditions.
    
    Parameters:
    - token: The trading token.
    - df: The DataFrame with resampled data.
    - current_positions: A dictionary of current positions.
    - state: The state object containing trading symbols and tokens.
    - delayed_entries: A dictionary to keep track of delayed entry signals.
    - delay_minutes: The delay in minutes before executing the trade.
    """
    timestamp = df.index[-1]
    direction = df['ce_direction'].iloc[-1]
    high = df['high'].iloc[-1]
    low = df['low'].iloc[-1]

    # Check if we should store a delayed entry signal
    if current_positions.get(token) is None:
        signal_bar_length = high - low
        if direction == 1:  # Bullish signal
            if signal_bar_length > 2 * (df['high'].iloc[-2] - df['low'].iloc[-2]):
                delayed_entries[token] = {'timestamp': timestamp, 'direction': direction, 'price': low}
        elif direction == -1:  # Bearish signal
            if signal_bar_length > 2 * (df['high'].iloc[-2] - df['low'].iloc[-2]):
                delayed_entries[token] = {'timestamp': timestamp, 'direction': direction, 'price': high}

    # Execute delayed entry if the delay period has passed
    if token in delayed_entries:
        entry_info = delayed_entries[token]
        if entry_info['timestamp'] is not None:
            delay_threshold = timestamp - pd.Timedelta(minutes=delay_minutes)
            if entry_info['timestamp'] <= delay_threshold:
                if entry_info['direction'] == 1:
                    entry_token = state.ce_trading_token
                    entry_symbol = state.ce_trading_symbol
                else:
                    entry_token = state.pe_trading_token
                    entry_symbol = state.pe_trading_symbol

                price = get_latest_price(entry_token)
                if price is not None:
                    log_trade(timestamp, entry_symbol, "ENTRY", price, pd.Timestamp.now())
                    current_positions[token] = 'long' if entry_info['direction'] == 1 else 'short'
                    delayed_entries[token] = {'timestamp': None, 'direction': None, 'price': None}



def process_token_data(token):
    df = resampled_data[token]

    if len(df) > atr_length:  # Ensure enough data for Chandelier Exit calculation

        # Extract Chandelier Exit values and direction
        chandelier_exit_long = df['long_stop'].iloc[-1]
        chandelier_exit_short = df['short_stop'].iloc[-1]
        direction = df['ce_direction'].iloc[-1]
        previous_chandelier_exit_long = df['long_stop'].iloc[-2]
        previous_chandelier_exit_short = df['short_stop'].iloc[-2]
        previous_direction = df['ce_direction'].iloc[-2]

        timestamp = df.index[-1]
        current_position = current_positions.get(token)
        action_taken = False

        # Check for exit signals based on Chandelier Exit
        if current_position == 'long' and df['low'].iloc[-1] < chandelier_exit_long:
            print(f"Long exit at {pd.Timestamp.now()}")
            
            op_token = entry_instruments.get(token, {}).get('op_token')
            op_symbol = entry_instruments.get(token, {}).get('op_symbol')
            
            price = get_latest_price(op_token)
            if price is not None:
                action_time = pd.Timestamp.now()
                log_trade(timestamp, op_symbol, "LONG_EXIT", price, action_time)
                print(f"Long Exit Signal for {op_symbol} at {timestamp} at {pd.Timestamp.now()}")
                current_positions[token] = None
                entry_prices[op_symbol] = None  # Clear the entry price
                action_taken = True

        elif current_position == 'short' and df['high'].iloc[-1] > chandelier_exit_short:
            print(f"Short exit at {pd.Timestamp.now()}")
            
            op_token = entry_instruments.get(token, {}).get('op_token')
            op_symbol = entry_instruments.get(token, {}).get('op_symbol')
            
            price = get_latest_price(op_token)
            if price is not None:
                action_time = pd.Timestamp.now()
                log_trade(timestamp, op_symbol, "SHORT_EXIT", price, action_time)
                print(f"Short Exit Signal for {op_symbol} at {timestamp} at {pd.Timestamp.now()}")
                current_positions[token] = None
                entry_prices[op_symbol] = None  # Clear the entry price
                action_taken = True

        # Then, handle delayed entries if we've just exited a position or if we're not in a position
        delayed_entry_logic(token, df, current_positions, state, delayed_entries, delay_minutes=1)
