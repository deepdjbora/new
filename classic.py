import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
import pandas as pd
import pyotp
from NorenRestApiPy.NorenApi import NorenApi

class TickCollector:
    def __init__(self, credentials_file="usercred.xlsx"):
        self.processing_lock = asyncio.Lock()
        self.api = None
        self.feed_opened = False
        self.ring_buffers = {}
        self.resampled_buffers = {}
        self.resampling_enabled = {}
        self.last_tick_time = {}
        self.active_subscriptions = set()
        self.RING_BUFFER_SIZE = 1000
        self.RING_BUFFER_RESAMPLE_SIZE = 1000
        self.VALID_TIMEFRAMES = ['1min', '5min']
        
        self.logger = self._setup_logger()
        self._initialize_api(credentials_file)

    def _setup_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def _initialize_api(self, credentials_file):
        self.api = NorenApi(
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

        self.api.login_result = self.api.login(
            userid=user,
            password=password,
            twoFA=factor2,
            vendor_code=vendor_code,
            api_secret=app_key,
            imei=imei
        )

    def create_ring_buffers(self, tokens):
        for token in tokens:
            if token not in self.ring_buffers:
                self.ring_buffers[token] = deque(maxlen=self.RING_BUFFER_SIZE)
                self.last_tick_time[token] = None
                self.logger.info(f"Created ring buffer for token: {token}")

    def create_resampled_buffers(self, tokens, timeframes):
        for token in tokens:
            if token not in self.resampled_buffers:
                self.resampled_buffers[token] = {}
                self.resampling_enabled[token] = {}
                self.logger.info(f"Created resampled buffers entry for token: {token}")
            
            for timeframe in timeframes:
                if timeframe not in self.resampled_buffers[token]:
                    self.resampled_buffers[token][timeframe] = deque(maxlen=self.RING_BUFFER_RESAMPLE_SIZE)
                    self.resampling_enabled[token][timeframe] = False
                    self.logger.info(f"Created resampled buffer for token {token} and timeframe: {timeframe}")

    async def set_resampling(self, token, timeframe, enable):
        if token in self.resampling_enabled and timeframe in self.resampling_enabled[token]:
            self.resampling_enabled[token][timeframe] = enable
            self.logger.info(f"Resampling {'enabled' if enable else 'disabled'} for token {token} and timeframe {timeframe}")
        else:
            self.logger.warning(f"Token {token} or timeframe {timeframe} not found in resampling_enabled")


    def event_handler_feed_update(self, tick_data):
        try:
            if 'lp' in tick_data and 'tk' in tick_data:
                timest = datetime.fromtimestamp(int(tick_data['ft'])).isoformat()
                token = tick_data['tk']
                if token in self.ring_buffers:
                    new_tick = {'tt': timest, 'ltp': float(tick_data['lp'])}
                    self.ring_buffers[token].append(new_tick)
                    self.last_tick_time[token] = datetime.fromisoformat(timest)
                    #self.logger.info(f"Added tick to buffer for token {token}. Ring_Buffer: {self.ring_buffers[token]}")
                else:
                    self.logger.warning(f"Token {token} not found in ring buffers. Ignoring tick.")
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error processing tick data: {e}")

 
    async def connect_and_subscribe(self):
        retry_delay = 1
        max_retry_delay = 32
        max_retries = 10
        retries = 0

        while retries < max_retries:
            try:
                self.api.start_websocket(
                    order_update_callback=self.event_handler_order_update,
                    subscribe_callback=self.event_handler_feed_update,
                    socket_open_callback=self.open_callback,
                    socket_close_callback=self.close_callback
                )
                await self.wait_for_feed_open(timeout=30)
                self.logger.info("WebSocket connected successfully.")
                
                await self.manage_subscriptions('add', 'MCX|432294')
                #await self.manage_subscriptions('add', 'NSE|26009')
                # await self.manage_subscriptions('add', 'NSE|26000')
                
                retry_delay = 1
                retries = 0
                await self.monitor_connection()
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                retries += 1
                self.logger.info(f"Reconnecting in {retry_delay} seconds... (Attempt {retries}/{max_retries})")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

        if retries >= max_retries:
            self.logger.error("Max retries reached. Exiting.")
            raise Exception("Max retries reached")

    async def manage_subscriptions(self, command, subscription):
        token = subscription.split('|')[1]

        if command == 'add':
            if subscription not in self.active_subscriptions:
                self.api.subscribe([subscription])
                self.active_subscriptions.add(subscription)
                self.create_ring_buffers([token])
                self.create_resampled_buffers([token], self.VALID_TIMEFRAMES)
                self.logger.info(f"Subscribed to {subscription}")
                for timeframe in self.VALID_TIMEFRAMES:
                    await self.set_resampling(token, timeframe, True)
                self.logger.info(f"Resampling enabled for token {token} for all valid timeframes.")
            else:
                self.logger.warning(f"Already subscribed to {subscription}")
        elif command == 'remove':
            if subscription in self.active_subscriptions:
                self.api.unsubscribe([subscription])
                self.active_subscriptions.remove(subscription)
                self.logger.info(f"Unsubscribed from {subscription}")
            else:
                self.logger.warning(f"Not subscribed to {subscription}")

    async def wait_for_feed_open(self, timeout):
        start_time = asyncio.get_event_loop().time()
        while not self.feed_opened:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("Timed out waiting for feed to open")
            await asyncio.sleep(1)

    async def monitor_connection(self):
        while True:
            if not self.feed_opened:
                self.logger.warning("Feed closed unexpectedly. Reconnecting...")
                raise Exception("Feed closed")
            await asyncio.sleep(5)

    def close_callback(self):
        self.feed_opened = False
        self.logger.warning("WebSocket connection closed.")
        self.logger.info("Attempting to reconnect...")

    def open_callback(self):
        if not self.feed_opened:
            self.feed_opened = True
            self.logger.info('Feed Opened')
        else:
            self.logger.warning('Feed Opened callback called multiple times.')

    def event_handler_order_update(self, data):
        self.logger.info(f"Order update: {data}")

    async def run(self):
        await asyncio.gather(
            self.connect_and_subscribe()            
        )

class DataProcessor:
    def __init__(self, tick_collector):
        self.tick_collector = tick_collector
        self.logger = logging.getLogger(__name__)
        self.last_processed_time = {}
        self.IDLE_THRESHOLD = timedelta(minutes=1)  # Adjust this as needed

    # async def ohlc_resampling(self):
    #     async with self.tick_collector.processing_lock:
    #         for token, ticks in self.tick_collector.ring_buffers.items():
    #             if not ticks:
    #                 self.logger.info(f"No ticks available for {token}")
    #                 continue
                
    #             # Create DataFrame from ticks
    #             df = pd.DataFrame(list(ticks))
    #             df['tt'] = pd.to_datetime(df['tt'])
    #             df.set_index('tt', inplace=True)
                
    #             #self.logger.info(f"Processing ticks for token {token}. Tick count: {len(df)}")

    #             # Iterate over each timeframe for OHLC resampling
    #             for timeframe in self.tick_collector.VALID_TIMEFRAMES:
    #                 if self.tick_collector.resampling_enabled[token].get(timeframe, False):
    #                     #self.logger.info(f"Resampling for token {token} at timeframe {timeframe}")

    #                     resampled = df['ltp'].resample(timeframe).ohlc()
                        
    #                     # Only update if we have valid resampled data
    #                     if not resampled.empty:
    #                         # Convert resampled data to dict and store in the resampled_buffers
    #                         resampled_records = resampled.reset_index().to_dict('records')
    #                         self.tick_collector.resampled_buffers[token][timeframe] = deque(
    #                             resampled_records,
    #                             maxlen=self.tick_collector.RING_BUFFER_RESAMPLE_SIZE
    #                         )
    #                         #self.logger.info(f"Updated resampled buffer for token {token} at timeframe {timeframe}. Resampled count: {len(resampled_records)}")
    #                     else:
    #                         self.logger.info(f"No resampled data for token {token} at timeframe {timeframe}")
    #                 else:
    #                     self.logger.info(f"Resampling not enabled for {token} at {timeframe}")
    async def ohlc_resampling(self):
        async with self.tick_collector.processing_lock:
            current_time = datetime.now()
            for token, ticks in self.tick_collector.ring_buffers.items():
                last_tick_time = self.tick_collector.last_tick_time.get(token)
                
                if last_tick_time is None:
                    self.logger.info(f"No last tick time available for {token}")
                    continue
                
                time_since_last_tick = current_time - last_tick_time
                
                if time_since_last_tick > self.IDLE_THRESHOLD:
                    self.logger.info(f"Token {token} idle for {time_since_last_tick}. Will process on next tick.")
                    continue
                
                if not ticks:
                    self.logger.info(f"No ticks available for {token}")
                    continue
                
                df = pd.DataFrame(list(ticks))
                df['tt'] = pd.to_datetime(df['tt'])
                df.set_index('tt', inplace=True)
                
                for timeframe in self.tick_collector.VALID_TIMEFRAMES:
                    if self.tick_collector.resampling_enabled[token].get(timeframe, False):
                        last_processed = self.last_processed_time.get((token, timeframe))
                        
                        if last_processed is None or last_tick_time > last_processed:
                            resampled = df['ltp'].resample(timeframe).ohlc().dropna()
                            
                            if not resampled.empty:
                                # Merge with existing data without filling gaps
                                existing_data = self.tick_collector.resampled_buffers[token].get(timeframe, deque())
                                existing_df = pd.DataFrame(list(existing_data)).set_index('tt') if existing_data else pd.DataFrame()
                                
                                if not existing_df.empty:
                                    # Remove any overlapping data
                                    existing_df = existing_df[existing_df.index < resampled.index[0]]
                                
                                # Concatenate existing data with new data
                                combined_df = pd.concat([existing_df, resampled])
                                
                                # Convert back to records and update the buffer
                                resampled_records = combined_df.reset_index().to_dict('records')
                                self.tick_collector.resampled_buffers[token][timeframe] = deque(
                                    resampled_records,
                                    maxlen=self.tick_collector.RING_BUFFER_RESAMPLE_SIZE
                                )
                                
                                self.last_processed_time[(token, timeframe)] = current_time
                                self.logger.info(f"Updated resampled buffer for {token} at {timeframe}. Resampled count: {len(resampled_records)}")
                            else:
                                self.logger.info(f"No resampled data for {token} at {timeframe}")
                        else:
                            self.logger.info(f"No new data for {token} at {timeframe} since last processing.")
                            
    async def process_data(self):
        #self.logger.info("DataProcessor: process_data method started")
        while True:
            #self.logger.info("DataProcessor: Starting OHLC resampling process...")
            await self.ohlc_resampling()
            await asyncio.sleep(1)  # Adjust the sleep time as needed

    def get_resampled_buffer_contents(self, token=None, timeframe=None):
    
        if token is None and timeframe is None:
            return {t: {tf: list(b) for tf, b in buffers.items()} 
                    for t, buffers in self.tick_collector.resampled_buffers.items()}
        elif token is not None and timeframe is None:
            return {tf: list(b) for tf, b in self.tick_collector.resampled_buffers.get(token, {}).items()}
        elif token is not None and timeframe is not None:
            return list(self.tick_collector.resampled_buffers.get(token, {}).get(timeframe, deque()))
        else:  # token is None and timeframe is not None
            return {t: list(buffers.get(timeframe, deque())) 
                    for t, buffers in self.tick_collector.resampled_buffers.items()}

    async def run(self):
        await asyncio.gather(
            self.process_data()            
        )
        
import nest_asyncio
# Global variable to store the DataProcessor instance
global_data_processor = None

async def main():
    global global_data_processor
    collector = TickCollector()
    processor = DataProcessor(collector)
    global_data_processor = processor
    
    await asyncio.gather(collector.run(), processor.run())

    
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Received exit signal. Cleaning up...")
    finally:
        loop.close()
        print("Event loop closed. Exiting.")