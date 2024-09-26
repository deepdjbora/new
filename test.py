# # FASTAPI
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List
import os

#Initialize FastAPI app
app = FastAPI()

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# List to keep track of connected WebSocket clients
connected_clients = []

from enum import Enum

class TradeEvent(Enum):
    TRADE_ENTERED = 'trade_entered'
    TRADE_UPDATED = 'trade_updated'
    TRADE_EXITED = 'trade_exited'

# Serve the HTML file at the root path
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    with open("static/index.html", "r") as file:
        return file.read()

# WebSocket endpoint for real-time updates
@app.websocket("/ws/trade_updates")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Keep the connection open
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

# Broadcast function to send updates to all connected clients

async def send_message_to_frontend(message):
    """
    Send a message to all connected WebSocket clients.
    
    message (dict): The message to be sent.
    """
    # Iterate over the connected clients and send the message to each one
    for client in connected_clients:
        try:
            await client.send_json(message)
        except WebSocketDisconnect:
            # If a client disconnects, remove it from the list
            connected_clients.remove(client)
        except Exception as e:
            # Log any other errors that may occur during the message broadcast
            logger.error(f"Error sending message to client: {e}")

async def broadcast_trade_update(trade_event, trade_data):
    """
    Broadcast trade-related updates to the frontend.
    
    trade_event (TradeEvent): The type of trade event.
    trade_data (dict): The data to be included in the broadcast message.
    """
    message = {
        'event': trade_event.value,
        'data': trade_data
    }
    
    # Broadcast the message to the frontend
    await send_message_to_frontend(message)
    
# # # FASTAPI 

import pandas as pd
# Load the CSV files into DataFrames
nfo_scrips_df = pd.read_csv('/home/deep/Desktop/NEWshoonya/NFO_symbols.csv')
mcx_scrips_df = pd.read_csv('/home/deep/Desktop/NEWshoonya/MCX_symbols.csv')

async def get_lotsize():
    global atm_strike
     
    while True:
        await asyncio.sleep(5)
        if exchange.upper() == 'NSE':
            df = nfo_scrips_df
        elif exchange.upper() == 'MCX':
            df = mcx_scrips_df
        else:
            raise ValueError("Unsupported exchange. Please use 'NSE' or 'MCX'.")

        # Find the first matching symbol
        match = df[df['Symbol'] == symbol]
        
        if not match.empty:
            # Get LotSize
            lotsize = match.iloc[0]['LotSize']
            
            # Check feedJson if token is provided
            if Initial_token:
                if not feedJson[Initial_token]:
                    logger.info(f"FeedJson for token {Initial_token} is empty. LotSize: {lotsize}.")                    
                else:
                    # Retrieve the last recent price
                    last_price = int(feedJson[Initial_token][-1]['ltp'])
                    # Calculate ATM strike price
                    mod = int(last_price) % 100
                    atm_strike = last_price - mod if mod <= 50 else last_price + (100 - mod)                    
                    # Find trading symbols for ATM strike
                    filtered_df = df[
                        (df['Symbol'] == symbol) &
                        (df['StrikePrice'] == float(atm_strike))
                    ]
                    
                    if filtered_df.empty:
                        logger.info(f"Could not find trading symbols for ATM strike {atm_strike}")
                        #return lotsize, last_price, None, None
                        logger.info(f"wait for lot size to update {lotsize}.")

                    # Find the CE and PE trading symbols
                    ce_row = filtered_df[filtered_df['OptionType'] == 'CE'].sort_values('Expiry').iloc[0]
                    pe_row = filtered_df[filtered_df['OptionType'] == 'PE'].sort_values('Expiry').iloc[0]

                    ce_trading_symbol, pe_trading_symbol = ce_row['TradingSymbol'], pe_row['TradingSymbol']
                    ce_trading_token, pe_trading_token = ce_row['Token'], pe_row['Token']                    
                    
                      # Update the state
                    state.ce_trading_symbol = ce_trading_symbol
                    state.pe_trading_symbol = pe_trading_symbol
                    state.ce_trading_token = ce_trading_token
                    state.pe_trading_token = pe_trading_token

                    #logger.info(f"CE Symbol: {ce_trading_symbol}, PE Symbol: {pe_trading_symbol}")            
        else:
            logger.warning(f"{symbol} not found on {exchange}.")

async def resample_ticks():
    global resampled_data
    last_timestamp = None
    
    while True:
        await asyncio.sleep(0.1)  # Reduced sleep time
        if not feedJson:
            continue

        with feed_lock:
            feed_data_copy = feedJson.copy()
        
        # Check for the latest tick timestamp to detect changes
        latest_timestamp = max([ticks[-1]['tt'] for token, ticks in feed_data_copy.items() if ticks])

        if latest_timestamp == last_timestamp:
            continue  # Skip if there's no new tick data

        temp_resampled_data = {}
        for token, ticks in feed_data_copy.items():
            if not ticks:
                continue
            
            df_new = pd.DataFrame(ticks)
            df_new["tt"] = pd.to_datetime(df_new["tt"])
            df_new.set_index("tt", inplace=True)

            current_resample_interval = df_new.index.max().floor(resample_frequency)

            if token not in resampled_data:
                df_resampled = df_new['ltp'].resample(resample_frequency).ohlc()
                temp_resampled_data[token] = df_resampled
                last_resample_time[token] = df_resampled.index.max()
            else:
                temp_df = resampled_data[token].copy()
                df_resampled = df_new['ltp'].resample(resample_frequency).ohlc()

                for idx, row in df_resampled.iterrows():
                    if idx in temp_df.index:
                        temp_df.loc[idx, 'high'] = max(temp_df.loc[idx, 'high'], row['high'])
                        temp_df.loc[idx, 'low'] = min(temp_df.loc[idx, 'low'], row['low'])
                        temp_df.loc[idx, 'close'] = row['close']
                    else:
                        temp_df.loc[idx] = row

                last_resample_time[token] = df_resampled.index.max()
                temp_resampled_data[token] = temp_df

            if token in temp_resampled_data:
                supertrend, su_direction = numba_indicators.supertrend_numba(
                    temp_resampled_data[token]['high'].values,
                    temp_resampled_data[token]['low'].values,
                    temp_resampled_data[token]['close'].values,
                    3,2
                )
                temp_resampled_data[token]['supertrend'] = supertrend
                temp_resampled_data[token]['su_direction'] = su_direction

                jma, ce_direction = numba_indicators.jma_numba_direction(
                    temp_resampled_data[token]['close'].values
                )
                temp_resampled_data[token]['jma'] = jma
                temp_resampled_data[token]['ce_direction'] = ce_direction

            temp_resampled_data[token] = temp_resampled_data[token].dropna(subset=['open', 'high', 'low', 'close'])

        with feed_lock:
            resampled_data = temp_resampled_data
           
        # Update the last feed data
        last_timestamp = latest_timestamp

async def candle_end_finder():
    global resampled_data, resample_frequency
    logger.info("Starting candle_end_finder")

    while True:
        current_time = pd.Timestamp.now()
        time_bucket_start = current_time.floor(resample_frequency)
        time_bucket_end = time_bucket_start + pd.Timedelta(resample_frequency)
        wait_time = (time_bucket_end - current_time).total_seconds() + 0.001

        if wait_time > 0:
            await asyncio.sleep(wait_time)

        data_copy = {}
        with feed_lock:
            if not resampled_data:
                logger.warning("resampled_data is empty.")
                continue

            # Copying the data outside of the lock to avoid data modification during processing
            for token, df in resampled_data.items():
                if df is None or df.empty:
                    logger.warning(f"DataFrame for token {token} is empty or None.")
                    continue

                data_copy[token] = df.copy()

        # Process each token's data outside of the lock
        for token, df in data_copy.items():
            logger.debug(f"Processing token: {token}")

            # Pre-emptive calculations outside the lock (if possible)
            previous_length = len(completed_candles_dfs[token]) if token in completed_candles_dfs else 0

            async with data_lock:               

                if token not in last_processed_candle or last_processed_candle[token] < time_bucket_end:
                    try:
                        if time_bucket_start == df.index[-1]:
                            # Only include the last candle if it matches the bucket start
                            completed_candles_dfs[token] = df
                            last_processed_candle[token] = time_bucket_start

                        elif time_bucket_end == df.index[-1]:
                            # If the end bucket matches, take all up to that point
                            completed_candles_dfs[token] = df.loc[:time_bucket_end - pd.Timedelta(microseconds=1)]
                            last_processed_candle[token] = time_bucket_start
                        else:
                            logger.error(f"No new candle forming now for token {token}")
                            continue

                        new_length = len(completed_candles_dfs[token])  # Calculate new_length inside the lock
                        rows_added = new_length - previous_length

                        if rows_added > 1:
                            logger.warning(f"Multiple rows ({rows_added}) added for token {token} at {pd.Timestamp.now()}. "
                                           f"Previous length: {previous_length}, New length: {new_length}")
                        # Verify that the required columns exist
                        try:
                            required_columns = ['ce_direction']
                            missing_columns = [col for col in required_columns if
                                               col not in completed_candles_dfs[token].columns]
                            if missing_columns:
                                raise KeyError(f"Missing columns {missing_columns}")

                        except KeyError as e:
                            logger.error(f"Error processing token {token}: {e}")

                    except KeyError as e:
                        logger.error(f"Error processing token {token}: Column {e} not found.")
                    except IndexError:
                        logger.error(f"Error processing token {token}: Not enough candles to calculate indicators.")
                logger.debug(f"candle_end_finder released data_lock for token {token}")

        # Calculate the time for the next bucket
        next_bucket_start = time_bucket_end
        wait_time = (next_bucket_start - pd.Timestamp.now()).total_seconds()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            
def get_latest_price_option(entry_instrument):
    entry_instrument_str = str(entry_instrument)
    with feed_lock:
        if entry_instrument_str in extra_feedJson:
            latest_data = extra_feedJson[entry_instrument_str][-1]
            latest_price = latest_data['ltp']            
            return latest_price
        else:
            print(f"{entry_instrument_str} not found in extra_feedJson")  # Debug print
            return None
        
def get_latest_price_index(entry_instrument):
    entry_instrument_str = str(entry_instrument)
    with feed_lock:
        if entry_instrument_str in feedJson:
            latest_data = feedJson[entry_instrument_str][-1]
            latest_price = latest_data['ltp']            
            return latest_price
        else:
            print(f"{entry_instrument_str} not found in feedJson")  # Debug print
            return None

async def direction_change_event_handler():
    last_changes = {}
    while True:        
        async with data_lock:            
            for token, df in completed_candles_dfs.items():
                if df.empty:
                    continue
                current_direction = df['ce_direction'].iloc[-1]
                second_direction = df['su_direction'].iloc[-1] 
                last_direction = last_changes.get(token, {}).get('ce_direction', None)

                # Check if the 'ce_direction' value has changed
                if last_direction is None or current_direction != last_direction:
                    logger.info(f"Direction change detected for token {token} at {df.index[-1]}: {current_direction}")
                    #await direction_change_queue.put((token, current_direction, last_direction, second_direction)) 
                    await direction_change_queue.put((1, token, current_direction, last_direction, second_direction))

                # Update last changes
                last_changes[token] = {'index': df.index[-1], 'ce_direction': current_direction}
        
        await asyncio.sleep(0.1)
    
async def process_direction_changes():
    while True:
        #token, current_direction, previous_direction, second_direction = await direction_change_queue.get() 
        priority, token, current_direction, previous_direction, second_direction = await direction_change_queue.get()

        try:
            await execute_trade_logic(token, current_direction, previous_direction, second_direction) 
        except Exception as e:
            logger.error(f"Error executing trade logic for {token}: {e}")

        direction_change_queue.task_done()
    
import asyncio
import nest_asyncio
import logging
import pandas as pd
import pyotp 
from asyncio import CancelledError
from collections import defaultdict, deque
from threading import Thread
from threading import Lock
from datetime import datetime
import numba_indicators
import uuid
from NorenRestApiPy.NorenApi import NorenApi

# Initialize logger
logger = logging.getLogger('ShoonyaApi')
logger.setLevel(logging.INFO) 
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

file_handler = logging.FileHandler('shoonya_api.log') # Replace 'shoonya_api.log' with your desired log file name
file_handler.setLevel(logging.INFO)  # Set the logging level for the file handler
# Apply the same formatter to the file handler
file_handler.setFormatter(formatter)
# Add the file handler to the logger
logger.addHandler(file_handler) 

# Global variables
completed_candles_dfs = defaultdict(pd.DataFrame)
last_processed_candle = defaultdict(pd.Timestamp)
direction_change_queue = asyncio.PriorityQueue() ##@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
use_second_direction = True
resampled_data = {}
last_resample_time = {}
monitoring_tasks = {}
current_positions = {}
feed_opened = False
feed_lock = Lock()
data_lock = asyncio.Lock()
position_lock = asyncio.Lock()
feedJson = defaultdict(lambda: deque(maxlen=20))
extra_feedJson = defaultdict(lambda: deque(maxlen=20))
api = None
exchange = 'NSE'
Initial_token = '26009'
subscription_string = f"{exchange}|{Initial_token}"
resample_frequency = "15s"
symbol = "BANKNIFTY"
atm_strike = int

# TRADE CONTROL flags 
enable_call_trades = True
enable_put_trades = True
enable_all_trades = True
force_exit_triggered = False

class TradingState:
    def __init__(self):
        self.ce_trading_symbol = None
        self.pe_trading_symbol = None
        self.ce_trading_token = None
        self.pe_trading_token = None
state = TradingState()

def initialize_api(credentials_file="usercred.xlsx"):
    global api
    api = NorenApi(
        host="https://api.shoonya.com/NorenWClientTP/",
        websocket="wss://api.shoonya.com/NorenWSTP/"
    )

    credentials = pd.read_excel(credentials_file)
    user = credentials.iloc[0, 0]
    password = credentials.iloc[0, 1]
    vendor_code = credentials.iloc[0, 2]
    app_key = credentials.iloc[0, 3]
    imei = credentials.iloc[0, 4]
    qr_code = credentials.iloc[0, 5]
    factor2 = pyotp.TOTP(qr_code).now()

    api.login_result = api.login(
        userid=user,
        password=password,
        twoFA=factor2,
        vendor_code=vendor_code,
        api_secret=app_key,
        imei=imei
    )

def event_handler_order_update(data):
    logger.info(f"Order update: {data}")

def event_handler_feed_update(tick_data):
    try:
        if 'lp' in tick_data and 'tk' in tick_data:
            timest = datetime.fromtimestamp(int(tick_data['ft'])).isoformat()
            token = tick_data['tk']

            with feed_lock:  # Acquire lock for thread-safety

                    if token == Initial_token:
                        feedJson[token].append({'ltp': float(tick_data['lp']), 'tt': timest})
                    else:
                        extra_feedJson[token].append({'ltp': float(tick_data['lp']), 'tt': timest})

    except (KeyError, ValueError) as e:
        logger.error(f"Error processing tick data: {e}")

async def connect_and_subscribe():
    global feed_opened
    retry_delay = 1  # Initial retry delay in seconds
    max_retry_delay = 32  # Maximum retry delay in seconds
    while True:
        try:
            api.start_websocket(
                order_update_callback=event_handler_order_update,
                subscribe_callback=event_handler_feed_update,
                socket_open_callback=open_callback,
                socket_close_callback=close_callback
            )
            await wait_for_feed_open(timeout=30)  # Wait for feed to open with a timeout
            api.subscribe([subscription_string])
            logger.info("WebSocket connected and subscribed successfully.")
            retry_delay = 1  # Reset retry delay after successful connection
            await monitor_connection()
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            logger.info(f"Reconnecting in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)  # Exponential backoff

async def wait_for_feed_open(timeout):
    global feed_opened
    start_time = asyncio.get_event_loop().time()
    while not feed_opened:
        if asyncio.get_event_loop().time() - start_time > timeout:
            raise TimeoutError("Timed out waiting for feed to open")
        await asyncio.sleep(1)

async def monitor_connection():
    global feed_opened
    while True:
        if not feed_opened:
            logger.warning("Feed closed unexpectedly. Reconnecting...")
            raise Exception("Feed closed")
        await asyncio.sleep(5)  # Check connection status every 5 seconds

def close_callback():
    global feed_opened
    feed_opened = False
    logger.warning("WebSocket connection closed.")

def open_callback():
    global feed_opened
    if not feed_opened:
        feed_opened = True
        logger.info('Feed Opened')
    else:
        logger.warning('Feed Opened callback called multiple times.')

async def main():   
    initialize_api()  
    websocket_task = asyncio.create_task(connect_and_subscribe())
    resample_task = asyncio.create_task(resample_ticks())
    lot_size_task = asyncio.create_task(get_lotsize()) 
    candle_end_finder_task = asyncio.create_task(candle_end_finder())     
    direction_change_event_handler_task = asyncio.create_task(direction_change_event_handler())
    process_direction_changes_task = asyncio.create_task(process_direction_changes())

    try:
        await asyncio.gather(
            websocket_task, lot_size_task, resample_task, candle_end_finder_task,
            direction_change_event_handler_task, process_direction_changes_task
        )   

    except asyncio.CancelledError:
        logger.info("Tasks cancelled. Shutting down...")

#Your existing event loop setup
loop = asyncio.get_event_loop()
loop.set_debug(True)
if loop.is_running():
    nest_asyncio.apply()

# Run the FastAPI application using uvicorn
async def run_fastapi():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

# Create a task for the FastAPI server
fastapi_task = asyncio.create_task(run_fastapi())

# Run the main trading bot tasks
asyncio.create_task(main())

# Run the event loop
if not loop.is_running():
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Received exit signal. Cleaning up...")
        # Add any cleanup code here
    finally:
        loop.close()
        logger.info("Event loop closed. Exiting.")
# Your existing event loop setup
# loop = asyncio.get_event_loop()
# loop.set_debug(True)
# if loop.is_running():
#     nest_asyncio.apply()
# asyncio.create_task(main())
# if not loop.is_running():
#     try:
#         loop.run_forever()
#     except KeyboardInterrupt:
#         logger.info("Received exit signal. Cleaning up...")
#         # Add any cleanup code here
#     finally:
#         loop.close()
#         logger.info("Event loop closed. Exiting.")

class TradeTracker:
    def __init__(self):
        self.total_trades = 0
        self.total_points_collected = 0
        self.total_points_lost = 0
        self.overall_profit_loss = 0
        self.win_trades = 0
        self.loss_trades = 0
        self.zero_pnl_trades = 0  # New attribute to track zero P/L trades

    async def update_stats(self, profit_loss):
        self.total_trades += 1

        if profit_loss > 0:
            self.win_trades += 1
            self.total_points_collected += profit_loss
        elif profit_loss < 0:
            self.loss_trades += 1
            self.total_points_lost += abs(profit_loss)
        else:  # Handle zero P/L trades
            self.zero_pnl_trades += 1
        self.overall_profit_loss += profit_loss

    async def print_summary(self):
        logger.info("Trade Summary:")
        logger.info(f"  Total Trades: {self.total_trades}")
        logger.info(f"  Win Trades: {self.win_trades}")
        logger.info(f"  Loss Trades: {self.loss_trades}")
        logger.info(f"  Zero P/L Trades: {self.zero_pnl_trades}")  # Add this line
        logger.info(f"  Total Points Collected: {self.total_points_collected:.2f}")
        logger.info(f"  Total Points Lost: {self.total_points_lost:.2f}")
        logger.info(f"  Overall Profit/Loss: {self.overall_profit_loss:.2f} points")

# Create a TradeTracker instance
trade_tracker = TradeTracker()

class HistoricalTrade:
    def __init__(self, trade_id, token, symbol_name, entry_price, position_type, entry_time=None, exit_time=None, exit_price=None, pnl=None):
        self.trade_id = trade_id  # Unique identifier (UUID)
        self.token = token
        self.symbol_name = symbol_name
        self.entry_price = entry_price
        self.position_type = position_type  # 'call_buy' or 'put_buy'
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.pnl = pnl

class HistoricalTradeTracker:
    def __init__(self):
        self.trades = {}  # Store trades by trade_id

    def add_trade(self, trade_id, trade):
        self.trades[trade_id] = trade

    def get_trade_by_id(self, trade_id):
        return self.trades.get(trade_id, None)

    def update_trade(self, trade_id, exit_time, exit_price, pnl):
        historical_trade = self.get_trade_by_id(trade_id)
        if historical_trade:
            historical_trade.exit_time = exit_time
            historical_trade.exit_price = exit_price
            historical_trade.pnl = pnl

    def print_historical_trades(self):
        logger.info("Historical Trades:")
        for trade in self.trades.values():
            entry_time = trade.entry_time or "N/A"
            exit_time = trade.exit_time or "N/A"
            exit_price = trade.exit_price if trade.exit_price is not None else "N/A"
            pnl = f"{trade.pnl:.2f}" if trade.pnl is not None else "N/A"
            
            logger.info(f"  Token: {trade.token}, Symbol: {trade.symbol_name}, Entry Time: {entry_time}, "
                        f"Entry Price: {trade.entry_price}, Exit Time: {exit_time}, "
                        f"Exit Price: {exit_price}, P/L: {pnl} points")

# Create an instance of HistoricalTradeTracker
historical_trade_tracker = HistoricalTradeTracker()

class Trade:
    # Class-level attribute for default SL
    default_sl_price = 5
    default_trailing_sl_price = 5

    def __init__(self, token, position_type, entry_price, option_token, symbol_name):
        self.token = token
        self.position_type = position_type
        self.entry_price = entry_price
        self.option_token = option_token
        self.symbol_name = symbol_name
        self.monitoring_task = None
        self.exit_event = asyncio.Event()
        self.exited = False  # Flag to indicate if the trade has exited
        self.trade_id = None  # Added trade_id attribute   @@@@@@@@@@@@@@@@@@@@@@@@@@@
        
        # Assign default SL and trailing SL from class-level attribute
        self.highest_price = entry_price
        self.target_price = entry_price + 20
        self.sl_price = entry_price - Trade.default_sl_price  # Use class-level default SL
        self.trailing_sl_price = entry_price - Trade.default_trailing_sl_price
        self.trail_activated = False
        self.trail_activation_point = 5

    @classmethod
    async def update_default_sl(cls, new_default_sl_price):
        """Update the class-level default SL price."""
        cls.default_sl_price = new_default_sl_price
        logger.info(f"Default SL updated globally to {cls.default_sl_price}")

    @classmethod
    async def update_default_trailing_sl(cls, new_default_trailing_sl_price):
        """Update the class-level default trailing SL price."""
        cls.default_trailing_sl_price = new_default_trailing_sl_price
        logger.info(f"Default trailing SL updated globally to {cls.default_trailing_sl_price}")

    async def update_sl(self, new_sl_price):
        """Update the stop loss price."""
        
        if not self.exited:
            self.sl_price = self.entry_price - new_sl_price
            logger.info(f"SL updated for {self.symbol_name} to {self.sl_price}")

    async def update_trailing_sl(self, new_trailing_sl_price):
        """Update the trailing stop loss price."""
        
        if not self.exited:
            self.trailing_sl_price = self.highest_price - new_trailing_sl_price
            self.trail_activated = True 
            logger.info(f"Trailing SL updated for {self.symbol_name} to {self.trailing_sl_price}")
    
    # Add a method to update the target price if needed
    async def update_target_price(self, new_target_price):
        if not self.exited:
            self.target_price = new_target_price
            logger.info(f"Target updated for {self.symbol_name} to {self.target_price}")

    async def force_exit(self, exit_reason="Forced Exit"):
        """Force exit the trade immediately."""
        
        if not self.exited:
            await exit_trade(self, exit_reason)
            logger.info(f"Trade forcibly exited for {self.symbol_name}")

async def monitor_position(trade):
    try:
        while not trade.exited:
            await asyncio.sleep(0.10)
            current_price = get_latest_price_option(trade.option_token)

            if current_price is None:
                continue

            # Broadcast the current price and trade status FASTAPI
            monitoring_data = {
                "trade_id": str(trade.trade_id),
                "token": trade.token,
                "symbol_name": trade.symbol_name,
                "current_price": current_price,
                "highest_price": trade.highest_price,
                "trailing_sl_price": trade.trailing_sl_price if trade.trail_activated else None                
            }
            await broadcast_trade_update(TradeEvent.TRADE_UPDATED, monitoring_data)
    

            if current_price >= trade.target_price:
                await exit_trade(trade, "Target Reached")
                break
            elif current_price <= trade.sl_price:
                await exit_trade(trade, "Stop Loss Hit")
                break
            elif not trade.trail_activated and current_price >= (trade.entry_price + trade.trail_activation_point):
                trade.trail_activated = True
                trade.trailing_sl_price = trade.entry_price
                logger.info(f"Trailing SL activated for {trade.symbol_name} at {trade.trailing_sl_price}")
            elif trade.trail_activated and current_price <= trade.trailing_sl_price:
                await exit_trade(trade, "Trailing Stop Loss Hit")
                break

            if current_price > trade.highest_price:
                trade.highest_price = current_price
                # if trade.trail_activated:
                #     trade.trailing_sl_price = trade.highest_price - (trade.trail_activation_point - 3)
        # Once the trade is exited, remove it from the UI
        
 
    except asyncio.CancelledError:
        logger.info(f"Monitoring cancelled for {trade.token} due to normal exit")
    except Exception as e:
        logger.error(f"Error in monitor_position for {trade.token}: {e}")
        
async def enter_trade(token, position_type, entry_type):
    try:
        option_token = state.ce_trading_token if position_type == "call_buy" else state.pe_trading_token
        symbol_name = state.ce_trading_symbol if position_type == "call_buy" else state.pe_trading_symbol

        entry_price = get_latest_price_option(option_token)  # Assuming this function exists
        if entry_price is None:
            logger.error(f"Unable to get entry price for {symbol_name}")
            return
        # Create a new Trade object
        # Create a unique identifier for the trade and its monitoring task
        trade_id = uuid.uuid4()
        trade = Trade(token, position_type, entry_price, option_token, symbol_name)
        trade.trade_id = trade_id

        # Update current_positions
        current_positions[token] = trade
        action_time = pd.Timestamp.now()
        logger.warning(f"Trade entered at {action_time} - {symbol_name} at {entry_price}")

        # Create a unique identifier for the trade and its monitoring task
        # trade_id = uuid.uuid4()
        trade.monitoring_task = asyncio.create_task(monitor_position(trade))
        monitoring_tasks[trade_id] = trade.monitoring_task

        historical_trade = HistoricalTrade(trade_id, token, symbol_name, entry_price, position_type, entry_time=action_time)
        historical_trade_tracker.add_trade(trade_id, historical_trade)

        # Place actual order using your brokerage API (replace with your actual order placement logic)
        # order_result = place_order(symbol_name, position_type, lot_size, entry_price)  # Example
        # logger.info(f"Order placed: {order_result}")

        # Broadcast the trade update to all connected clients FASTAPI
        trade_data = {
            "trade_id": str(trade_id),
            "token": token,
            "symbol_name": symbol_name,
            "entry_price": entry_price,
            "position_type": position_type,
            "entry_time": action_time.isoformat()
        }
        await broadcast_trade_update(TradeEvent.TRADE_ENTERED, trade_data)

    except Exception as e:
        logger.error(f"Error in enter_trade for {token}: {e}")
        raise

async def exit_trade(trade, exit_type):    
    try:
        exit_price = get_latest_price_option(trade.option_token)  # Assuming this function exists
        if exit_price is None:
            logger.error(f"Unable to get exit price for {trade.symbol_name}")
            return

        profit_loss = (exit_price - trade.entry_price) 

        action_time = pd.Timestamp.now()
        logger.warning(f"Trade exited at {action_time} - {trade.symbol_name} at {exit_price}. {exit_type}. P/L: {profit_loss:.2f} points")

        # Broadcast the exit reason and other details FASTAPI
        exit_data = {
            "trade_id": str(trade.trade_id),
            "token": trade.token,
            "symbol_name": trade.symbol_name,
            "exit_price": exit_price,
            "exit_reason": exit_type,
            "profit_loss": profit_loss,
            "exit_time": action_time.isoformat()
        }
        await broadcast_trade_update(TradeEvent.TRADE_EXITED, exit_data)


        # Mark the trade as exited and cancel the monitoring task
        trade.exited = True
        if trade.monitoring_task:
            trade_id = next((tid for tid, task in monitoring_tasks.items() if task == trade.monitoring_task), None)
            if trade_id:
                monitoring_tasks[trade_id].cancel()
                del monitoring_tasks[trade_id]        
        await trade_tracker.update_stats(profit_loss)

        historical_trade_tracker.update_trade(trade_id, exit_time=action_time, exit_price=exit_price, pnl=profit_loss)

        # Place actual exit order using your brokerage API (replace with your actual order placement logic)
        # order_result = place_exit_order(trade.symbol_name, trade.position_type, lot_size, exit_price)  # Example
        # logger.info(f"Exit order placed: {order_result}")

    except Exception as e:
        logger.error(f"Error in exit_trade for {trade.token}: {e}")
        raise

async def execute_trade_logic(token, current_direction, previous_direction, second_direction):
    global current_positions, position_lock

    # 1. Check for active trade outside the lock (read-only operation)
    active_trade = next((trade for trade in current_positions.values() if not trade.exited), None)

    if active_trade:
        exit_signal = (
            (active_trade.position_type == 'call_buy' and current_direction == -1 and previous_direction == 1) or
            (active_trade.position_type == 'put_buy' and current_direction == 1 and previous_direction == -1)
        )

        if exit_signal:
            async with position_lock:  # Acquire lock only for exiting the trade
                try:
                    logger.warning("exiting")
                    await exit_trade(active_trade, "Regular Exit")
                except Exception as e:
                    print(f"Error exiting trade for {token}: {e}")

                # After exiting, set active_trade to None
                active_trade = None

    if not active_trade:
        entry_signal = False

        # 2. Calculate entry signal outside the lock
        if use_second_direction:
            second_direction_valid = second_direction == current_direction
        else:
            second_direction_valid = True

        if current_direction == 1 and previous_direction == -1 and enable_call_trades and enable_all_trades and second_direction_valid:
            position_type = "call_buy"
            entry_signal = True
        elif current_direction == -1 and previous_direction == 1 and enable_put_trades and enable_all_trades and second_direction_valid:
            position_type = "put_buy"
            entry_signal = True

        if entry_signal:
            # 3. Check candle significance outside the lock
            df = completed_candles_dfs[token]
            high = df['high'].values
            low = df['low'].values
            is_significant, avg_height, current_height = numba_indicators.check_significant_candle(high, low)

            if not is_significant:
                async with position_lock:  # Acquire lock only for entering the trade
                    try:
                        logger.warning("entering normal trade.")
                        await enter_trade(token, position_type, "Regular Entry")
                    except Exception as e:
                        print(f"Error entering trade for {token}: {e}")
            else:
                logger.warning(f"Skipping entry due to significant candle. Avg height: {avg_height}, Current height: {current_height}")
                    # Start monitoring for 50% retracement
                    #asyncio.create_task(monitor_retracement(token, position_type, current_height, df['close'].iloc[-1], current_direction))
