 
import json
import os
import time
import logging
from datetime import datetime
from pya3 import Aliceblue

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load API Key securely (Set these as environment variables)
USER_ID = "928693" 
API_KEY = "EqF9mkSCkRzyMFpGCG9QSEOeTmus6J8OPTEvilpyg8C2OkuVeCGM6fHApSq66dpVhgISIhpnqodmlppKlf1CvudNlJBOA1ycdhmtermzmM9IEidC2ByATqSyU2qEjaBx" 

# Initialize Aliceblue API session
alice = Aliceblue(user_id=USER_ID, api_key=API_KEY)
alice.get_session_id()

# WebSocket Variables
LTP = 0
socket_opened = False
subscribe_flag = False
subscribe_list = []
unsubscribe_list = []

# File to store tick data
TICK_DATA_FILE = "tick_data1.txt"

# Callback Functions
def socket_open():
    """Callback when WebSocket connects successfully"""
    global socket_opened
    logging.info("WebSocket Connected")
    socket_opened = True
    if subscribe_flag:
        alice.subscribe(subscribe_list)

def socket_close():
    """Callback when WebSocket closes"""
    global socket_opened, LTP
    socket_opened = False
    LTP = 0
    logging.warning("WebSocket Closed. Attempting Reconnect...")
    time.sleep(5)  # Delay before reconnection
    reconnect_websocket()

def socket_error(message):
    """Callback for WebSocket errors"""
    global LTP
    LTP = 0
    logging.error(f"WebSocket Error: {message}")

def feed_data(message):
    """Callback for live market feed"""
    global LTP, subscribe_flag
    feed_message = json.loads(message)
    
    if feed_message["t"] == "ck":
        logging.info(f"Connection Acknowledgement: {feed_message['s']} (WebSocket Connected)")
        subscribe_flag = True
    elif feed_message["t"] == "tk":
        logging.info(f"Token Acknowledgement: {feed_message}")
    else:
        LTP = feed_message.get("lp", LTP)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tick_data = f"{timestamp}, {feed_message}\n"

    # Store tick data in file
    with open(TICK_DATA_FILE, "a") as file:
        file.write(tick_data)   

def reconnect_websocket():
    """Reconnect WebSocket after disconnection"""
    alice.start_websocket(
        socket_open_callback=socket_open,
        socket_close_callback=socket_close,
        socket_error_callback=socket_error,
        subscription_callback=feed_data,
        run_in_background=True,
        market_depth=False
    )

# Start WebSocket Connection
reconnect_websocket()

# Wait until socket is opened before subscribing
while not socket_opened:
    time.sleep(1)

# Subscribe to Nifty 50 Index (Token: 26000)
subscribe_list = [alice.get_instrument_by_token('NSE', 1594)]
alice.subscribe(subscribe_list)

logging.info(f"Subscribed to: {subscribe_list}")
logging.info(f"Script started at: {datetime.now()}")

# Keep the script running to maintain WebSocket connection
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Script interrupted by user. Stopping WebSocket.")
    alice.stop_websocket()
