import asyncio

# Global dictionaries to keep track of active tasks
retracement_tasks = {}
exit_monitoring_tasks = {}

async def execute_trade_logic(token, current_direction, previous_direction, completed_candles_df):
    global current_positions, position_lock, retracement_tasks, exit_monitoring_tasks
    print("I am execute_trade_logic")

    async with position_lock:
        # Exit Logic (Prioritized)
        if token in current_positions:
            position_data = current_positions[token]
            op_token = position_data["option_token"]
            op_symbol = position_data["symbol_name"]
            position_type = position_data["position_type"]

            if (position_type == 'call_buy' and current_direction == -1 and previous_direction == 1) or \
               (position_type == 'put_buy' and current_direction == 1 and previous_direction == -1):
                try:
                    logger.warning("exiting")
                    await exit_trade(token, position_type, op_token, op_symbol, "Regular Exit")
                    
                    # Cancel exit monitoring task for this token
                    if token in exit_monitoring_tasks:
                        exit_monitoring_tasks[token].cancel()
                        del exit_monitoring_tasks[token]
                except Exception as e:
                    print(f"Error exiting trade for {token}: {e}")

        # Entry Logic 
        if token not in current_positions:  
            entry_signal = False
            if current_direction == 1 and previous_direction == -1: 
                position_type = "call_buy"
                entry_signal = True
            elif current_direction == -1 and previous_direction == 1:
                position_type = "put_buy"
                entry_signal = True

            if entry_signal:
                # Check if the last candle is significantly larger than average
                if is_significant_candle(completed_candles_df):
                    # Start monitoring for retracement
                    if token not in retracement_tasks:
                        task = asyncio.create_task(monitor_retracement(token, position_type, completed_candles_df))
                        retracement_tasks[token] = task
                else:
                    # Normal entry if the candle is not significant
                    try:
                        logger.warning("entering normal trade.")
                        await enter_trade(token, position_type, "Regular Entry")
                        # Start exit monitoring task
                        task = asyncio.create_task(monitor_exit(token, position_type))
                        exit_monitoring_tasks[token] = task
                    except Exception as e:
                        print(f"Error entering trade for {token}: {e}")

async def monitor_retracement(token, position_type, initial_candle_df):
    global feedJson, current_positions

    high = initial_candle_df['high'].iloc[-1]
    low = initial_candle_df['low'].iloc[-1]
    retracement_level = low + RETRACEMENT_THRESHOLD * (high - low)
    initial_direction = 1 if position_type == "call_buy" else -1

    try:
        while True:
            await asyncio.sleep(0.1)  # Small delay to prevent excessive CPU usage

            with feed_lock:
                if token not in feedJson or not feedJson[token]:
                    continue

                current_price = feedJson[token][-1]['ltp']
                current_direction = get_current_direction(token)

                # Check if direction has changed
                if current_direction != initial_direction:
                    logger.warning(f"Direction changed for {token}. Stopping retracement monitoring.")
                    break

                # Check if price is near retracement level
                if low <= current_price <= high and abs(current_price - retracement_level) / (high - low) < 0.01:
                    retracement_direction = 1 if current_price > retracement_level else -1
                    if (position_type == "call_buy" and retracement_direction == 1) or \
                       (position_type == "put_buy" and retracement_direction == -1):
                        await enter_trade(token, position_type, "Retracement Entry")
                        logger.warning(f"Retracement entry executed for {token}")
                        # Start exit monitoring task
                        task = asyncio.create_task(monitor_exit(token, position_type))
                        exit_monitoring_tasks[token] = task
                        break
    finally:
        # Remove the task from retracement_tasks when done
        if token in retracement_tasks:
            del retracement_tasks[token]

async def monitor_exit(token, position_type):
    global extra_feedJson, current_positions

    try:
        while True:
            await asyncio.sleep(0.1)  # Small delay to prevent excessive CPU usage

            if token not in current_positions:
                break  # Exit if position is closed

            position = current_positions[token]
            option_token = position['option_token']
            entry_price = position.get('entry_price')

            if entry_price is None:
                continue

            with feed_lock:
                if option_token in extra_feedJson and extra_feedJson[option_token]:
                    current_option_price = extra_feedJson[option_token][-1]['ltp']
                    
                    # Check for target (e.g., 20% profit)
                    if current_option_price >= entry_price * 1.2:
                        await exit_trade(token, position_type, option_token, position['symbol_name'], "Target Hit")
                        break
                    
                    # Check for stop loss (e.g., 10% loss)
                    elif current_option_price <= entry_price * 0.9:
                        await exit_trade(token, position_type, option_token, position['symbol_name'], "Stop Loss Hit")
                        break
    finally:
        # Remove the task from exit_monitoring_tasks when done
        if token in exit_monitoring_tasks:
            del exit_monitoring_tasks[token]

# Implement these functions based on your specific logic
def is_significant_candle(completed_candles_df):
    # Implementation here
    pass

def get_current_direction(token):
    # Implementation here
    pass

async def enter_trade(token, position_type, entry_reason):
    # Implementation here
    pass

async def exit_trade(token, position_type, op_token, op_symbol, exit_reason):
    # Implementation here
    pass