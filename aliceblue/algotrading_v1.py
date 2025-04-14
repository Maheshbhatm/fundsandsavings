import json
import os
import time
import logging
import pandas as pd
import ast
import re
import requests
from datetime import datetime
from pya3 import Aliceblue
import threading 
import sys
import signal


# Configure Logging
logging.basicConfig(level=logging.INFO, format="\r%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

# API Credentials (Should be stored securely)
USER_ID = "928693"
API_KEY = "EqF9mkSCkRzyMFpGCG9QSEOeTmus6J8OPTEvilpyg8C2OkuVeCGM6fHApSq66dpVhgISIhpnqodmlppKlf1CvudNlJBOA1ycdhmtermzmM9IEidC2ByATqSyU2qEjaBx"
alice = Aliceblue(user_id=USER_ID, api_key=API_KEY)
alice.get_session_id()

# WebSocket Variables
LTP = 0
socket_opened = False
subscribe_flag = False
subscribe_list = []
unsubscribe_list = []

# Constants
instrument_tokens = [17869,4067,1512,18921,772,1270,3787,404,17438,15355,1660,3063,20374,14299,3426,11630,1406,29135,11351,526,14977,18143,383,2475,5097,4668,438,15332,212,4717,4204,1624,3499,2029,10753,10794,10666,17400,11915,14366]
TICK_DATA_FILE = "tick_data11Feb.txt"
SUMMARY_DATA_FILE = "summary_data.txt"
TRADE_DATA_FILE = "trade_data_file.txt"
TOP_LOSSER_COUNT = 3 
EXPIRY_MONTH = "FEB"
BASE_URL = "https://api.aliceblueonline.com"

# Read NSE Data
nse_df = pd.read_csv("NSE.csv")

live_prices = {}

#  Track Execution Time
start_time = datetime.now()
end_time = start_time.replace(hour=9, minute=25, second=0, microsecond=0)  # Stop at 9:25 AM

# ----------------------------------------------------------------
# ✅ FUNCTION: Collect Market Data (9:15 - 9:25 AM)
# ----------------------------------------------------------------
def collect_market_data():
    """Collect market data from 9:15 AM to 9:25 AM."""
    logging.info("Starting Market Data Collection (9:15 AM - 9:25 AM)...")
    
    while datetime.now() < end_time:
        time.sleep(1)  # Keep running until 9:25 AM
    
    logging.info("Market Data Collection Completed at 9:25 AM.")
    process_tick_data()

# ----------------------------------------------------------------
# ✅ FUNCTION: Process Tick Data
# ----------------------------------------------------------------
def process_tick_data():
    """Process collected tick data and compute stock movements."""
    logging.info("Processing Tick Data...")

    with open(TICK_DATA_FILE, "r") as file:
        raw_text = file.read()

    data = []
    for line in raw_text.strip().split('\n'):
        try:
            timestamp, dict_str = line.split(", ", 1)
            dict_data = json.loads(dict_str)
            dict_data['timestamp'] = timestamp
            data.append(dict_data)
        except Exception as e:
            logging.warning(f"Skipping malformed line: {line} | Error: {e}")

    df = pd.DataFrame(data)

    if df.empty:
        logging.error("No tick data available for processing.")
        return None

    # Process Data
    df['lp'] = df['lp'].astype(float)
    summary = df.groupby('tk').agg(
        open_price=('lp', 'first'),
        close_price=('lp', 'last'),
        high=('lp', 'max'),
        low=('lp', 'min')
    ).reset_index()

    summary['gap'] = summary['close_price'] - summary['open_price']
    summary['percentage_change'] = (summary['gap'] / summary['open_price']) * 100
    summary['label'] = summary['percentage_change'].apply(lambda x: 'Gainer' if x > 0 else 'Loser')

    summary.rename(columns={'tk': 'token', 'open_price': 'open', 'close_price': 'close'}, inplace=True)
    summary.to_csv(SUMMARY_DATA_FILE, index=False)

    logging.info("Tick Data Processed & Summary Saved.")

# ----------------------------------------------------------------
# ✅ FUNCTION: Identify Top Losers & Subscribe to Their Options
# ----------------------------------------------------------------
def get_top_losers():
    """Fetch top 3 losing stocks and subscribe to their options."""
    logging.info("Identifying Top Losers...")
    
    df = pd.read_csv(SUMMARY_DATA_FILE)
    df_sorted = df.sort_values(by="percentage_change")
    df_top_loser = df_sorted.head(TOP_LOSSER_COUNT)

    logging.info(f"Top {TOP_LOSSER_COUNT} Losers:\n{df_top_loser}")

    # Merge with NSE Data
    top_loser_df = df_top_loser.merge(nse_df, how='left', right_on='Token', left_on='token')

    # Fetch NFO Contract Data
    nfo_contract_df = fetch_nfo_contract_data()
    if nfo_contract_df is None:
        return top_loser_df  # Return without options data if fetch fails

    # Find ATM Strike Price for Each Stock
    merged_data = []
    for _, row in top_loser_df.iterrows():
        symbol, close_price_stock = row['Symbol'], row['close']
        df_options = nfo_contract_df[
            (nfo_contract_df['symbol'] == symbol) &
            (nfo_contract_df['instrument_type'] == 'OPTSTK') &
            (nfo_contract_df['option_type'] == 'PE') &
            (nfo_contract_df['formatted_ins_name'].str.contains(EXPIRY_MONTH, na=False))
        ]

        df_options['strike_price'] = pd.to_numeric(df_options['strike_price'], errors='coerce')
        atm_strike_row = df_options.loc[(df_options['strike_price'] - close_price_stock).abs().idxmin()].to_dict() if not df_options.empty else {}

        merged_data.append({**row.to_dict(), **atm_strike_row})

    df_top_losers = pd.DataFrame(merged_data)
    df_top_losers.to_csv("top_losers.csv", index=False)

    # Subscribe to Top 3 Losers and Their Options
    subscribe_to_losers(df_top_losers)
    
    return df_top_losers

# ----------------------------------------------------------------
# ✅ FUNCTION: Subscribe to Top Losers for Live Trading
# ----------------------------------------------------------------
def subscribe_to_losers(df_top_losers):
    """Subscribe to top losers and their corresponding options."""
    stock_tokens = df_top_losers["token"].tolist()
    option_tokens = df_top_losers["Token"].tolist()
    all_tokens = stock_tokens + option_tokens

    logging.info(f"Subscribing to Tokens: {all_tokens}")
    subscribe_list = [alice.get_instrument_by_token('FNO', token) for token in all_tokens]
    alice.subscribe(subscribe_list)
# ----------------------------------------------------------------
# ✅ FUNCTION: Place Trade Order
# ----------------------------------------------------------------
def place_trade(order_details):
    """Place a trade order using AliceBlue API."""
    url = f"{BASE_URL}/place_order"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {USER_ID} SESSION_TOKEN'}
    response = requests.post(url, headers=headers, data=json.dumps(order_details))
    logging.info(f"Trade Response: {response.text}")

# ----------------------------------------------------------------
# ✅ FUNCTION: Fetch NFO Contracts
# ----------------------------------------------------------------
def fetch_nfo_contract_data():
    """Fetch option contract data from AliceBlue."""
    url = "https://v2api.aliceblueonline.com/restpy/contract_master?exch=NFO"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return pd.DataFrame(data["NFO"]) if "NFO" in data else None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching NFO data: {e}")
        return None

# ----------------------------------------------------------------
# ✅ FUNCTION: Execute Trade for Top Losers
# ----------------------------------------------------------------
def execute_trade_for_losers(summary_df):
    losers = summary_df[summary_df['label'] == 'Loser'].nsmallest(TOP_LOSSER_COUNT, 'low')
    for _, row in losers.iterrows():
        order_details = [{
            "complexty": "co",
            "discqty": "0",
            "exch": "NSE",
            "pCode": "mis",
            "prctyp": "SL",
            "price": row['low'] - 1,
            "qty": 10,
            "ret": "DAY",
            "stopLoss": 5,
            "symbol_id": str(row['token']),
            "target": 5,
            "trading_symbol": "SYMBOL_PLACEHOLDER",
            "trailing_stop_loss": 2,
            "transtype": "sell",
            "trigPrice": row['low'],
            "orderTag": "order1",
            "deviceNumber": "sdagds345324dsfgfvasdqwr4"
        }]
        # place_trade(order_details)
 
# ----------------------------------------------------------------
# ✅ WebSocket Callbacks
# ----------------------------------------------------------------
def socket_open():
    global socket_opened
    logging.info("WebSocket Connected")
    socket_opened = True
    if subscribe_flag:
        alice.subscribe(subscribe_list)

def socket_close():
    global socket_opened, LTP
    socket_opened = False
    LTP = 0
    logging.warning("WebSocket Closed. Attempting Reconnect...")
    time.sleep(5)
    reconnect_websocket()

def socket_error(message):
    global LTP
    LTP = 0
    logging.error(f"WebSocket Error: {message}")

def feed_data(message):
    global LTP, subscribe_flag
    feed_message = json.loads(message)
    
    if feed_message["t"] == "ck":
        subscribe_flag = True
    elif feed_message["t"] == "tk":
        pass
    else:
        LTP = feed_message.get("lp", LTP)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tick_data = f"{timestamp}, {feed_message}\n"
        
        with open(TICK_DATA_FILE, "a") as file:
            file.write(tick_data)
        
        update_summary()

# ----------------------------------------------------------------
# ✅ FUNCTION: Reconnect WebSocket
# ----------------------------------------------------------------
def reconnect_websocket():
    if not socket_opened:
        alice.start_websocket(
            socket_open_callback=socket_open,
            socket_close_callback=socket_close,
            socket_error_callback=socket_error,
            subscription_callback=feed_data,
            run_in_background=True,
            market_depth=False
        )
# ----------------------------------------------------------------
# ✅ FUNCTION: Update Summary File
# ----------------------------------------------------------------
def update_summary_file(summary_df):
    summary_df = summary_df.sort_values(by='percentage_change', ascending=True)
    summary_df.to_csv(SUMMARY_DATA_FILE, index=False)

def run_live_algo():
    reconnect_websocket()

    while not socket_opened:
        time.sleep(1) 

    subscribe_list = [alice.get_instrument_by_token('NSE', token) for token in instrument_tokens]
    alice.subscribe(subscribe_list)

    logging.info(f"Subscribed to: {subscribe_list}")
    logging.info(f"Script started at: {datetime.now()}")
 
def update_summary():
    summary_df = process_tick_data()

    if summary_df is not None:
        update_summary_file(summary_df)
        # execute_trade_for_losers(summary_df)

def handle_exit(signum, frame):
    logging.info("Received exit signal. Stopping WebSocket...")
    alice.stop_websocket()
    sys.exit(0)
 
signal.signal(signal.SIGINT, handle_exit)  # Handles Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # Handles system kill signals

# Main Function 
run_live_algo()

try:
    while True:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    handle_exit(None, None)
 

def get_top_loosers_fnc():
    df = pd.read_csv(SUMMARY_DATA_FILE)
    df_sorted = df.sort_values(by="percentage_change")
    df_top_loser = df_sorted.head(TOP_LOSSER_COUNT)
    print(df_top_loser)

    top_loser_tokens = df_top_loser["token"].tolist()
    print(f" Top {TOP_LOSSER_COUNT} Tokens : {top_loser_tokens}")

    # unsubcribe to the all other tokens 
    tokens_to_unsubscribe = [token for token in instrument_tokens if token not in top_loser_tokens]
    # unsubscribe_list = [alice.get_instrument_by_token('NSE', token) for token in tokens_to_unsubscribe]
    # alice.unsubscribe(unsubscribe_list)
  
    top_loser_df = df_top_loser.merge(nse_df, how='left', right_on='Token', left_on='token')
 
    nfo_contract_df = fetch_nfo_contract_data()   

    merged_data = []  
    for index, row in top_loser_df.iterrows():
        
        symbol = row['Symbol']   
        close_price_stock = row['close']    

        # Filter option contracts for the stock (PUT options expiring in February)
        df_options = nfo_contract_df[
            (nfo_contract_df['symbol'] == symbol) & 
            (nfo_contract_df['instrument_type'] == 'OPTSTK') &  
            (nfo_contract_df['option_type'] == 'PE') &  
            (nfo_contract_df['formatted_ins_name'].str.contains(EXPIRY_MONTH, na=False))
        ]
        df_options['strike_price'] = pd.to_numeric(df_options['strike_price'], errors='coerce')

        if not df_options.empty: 
            atm_strike_row = df_options.loc[(df_options['strike_price'] - close_price_stock).abs().idxmin()]
            atm_strike_row = atm_strike_row.to_dict()  
        else:
            atm_strike_row = {col: None for col in nfo_contract_df.columns}  

        merged_row = {**row.to_dict(), **atm_strike_row}  
        merged_data.append(merged_row) 

    df_merged_nse_nfo = pd.DataFrame(merged_data) 
    return df_merged_nse_nfo   

 
df_merged_nse_nfo = get_top_loosers_fnc()

# Function to Check for Breakdown and Take Trade
def check_for_breakdown_and_trade(token, current_price):
    df_row = df_merged_nse_nfo[df_merged_nse_nfo["token"] == token]

    if not df_row.empty:
        low_price = df_row["low"].values[0]
        option_token = df_row["Token"].values[0]  # FNO Option Token
        trading_symbol = df_row["trading_symbol"].values[0]
        strike_price = float(df_row["strike_price"].values[0])

        if current_price < low_price:
            logging.info(f"Stock Breakdown: {trading_symbol} | Current: {current_price} | Low: {low_price}")
            print(f"Stock Breakdown: {trading_symbol} | Buying OPTION {strike_price} ")
            # place_put_trade(option_token, trading_symbol, strike_price)
        else:
            logging.info(f"{trading_symbol} is above low: {current_price} > {low_price}")


def feed_data(message):
    global live_prices
    feed_message = json.loads(message)

    if feed_message["t"] == "tk":
        return

    token = feed_message.get("tk")
    current_price = feed_message.get("lp")

    if token and current_price:
        live_prices[token] = current_price
        check_for_breakdown_and_trade(token, current_price)

def run_live_trading():
    reconnect_websocket()

    while not live_prices:
        time.sleep(1)

    # Subscribe to both Stock & Option tokens
    stock_tokens = df_merged_nse_nfo["token"].tolist()
    option_tokens = df_merged_nse_nfo["Token"].tolist()
    all_tokens = stock_tokens + option_tokens

    # subscribe_list = [alice.get_instrument_by_token('FNO', token) for token in all_tokens]
    # alice.subscribe(subscribe_list)

    logging.info(f"Subscribed to Tokens: {all_tokens}")

# Run Live Trading
run_live_trading()


