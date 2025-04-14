import json
import time
import logging
import pandas as pd
import requests
from datetime import datetime
from pya3 import Aliceblue
import sys
import signal

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ API Credentials
USER_ID = "928693"
API_KEY = "EqF9mkSCkRzyMFpGCG9QSEOeTmus6J8OPTEvilpyg8C2OkuVeCGM6fHApSq66dpVhgISIhpnqodmlppKlf1CvudNlJBOA1ycdhmtermzmM9IEidC2ByATqSyU2qEjaBx"

# ✅ Initialize AliceBlue API session
alice = Aliceblue(user_id=USER_ID, api_key=API_KEY)
alice.get_session_id()

# ✅ Constants
INSTRUMENT_TOKENS = [17869,4067,1512,18921,772,1270,3787,404,17438,15355]
TICK_DATA_FILE = "tick_data12feb.txt"
SUMMARY_DATA_FILE = "summary_data__2025-02-13.txt"
SUBSCRIBED_TOKENS_FILE = 'subs_tokens_file.txt'
TOP_LOSSER_COUNT = 3
EXPIRY_MONTH = "FEB"
BASE_URL = "https://api.aliceblueonline.com"
live_prices = {}

# ✅ Read NSE Data
nse_df = pd.read_csv("NSE.csv")

# ✅ Track Execution Time
start_time = datetime.now()
end_time = start_time.replace(hour=9, minute=25, second=0, microsecond=0)  # Stop at 9:25 AM

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
# ✅ FUNCTION: WebSocket Callbacks
# ----------------------------------------------------------------
def feed_data(message):
    """Process live tick data & store in TICK_DATA_FILE."""
    try:
        feed_message = json.loads(message)

        if feed_message["t"] in ["ck", "tk"]:  # Ignore control messages
            return

        token = feed_message.get("tk")
        last_price = feed_message.get("lp")

        if token is not None and last_price is not None:
            # ✅ Store the latest price in live_prices dictionary
            live_prices[token] = last_price

            # ✅ Save tick data in file for post 9:25 AM processing
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tick_data = f"{timestamp}, {json.dumps(feed_message)}\n"

            with open(TICK_DATA_FILE, "a") as file:
                file.write(tick_data)

            logging.info(f"📝 Tick Data Stored: {tick_data.strip()}")

    except Exception as e:
        logging.error(f"❌ Error in feed_data: {e}")


      

def reconnect_websocket():
    """Ensures WebSocket stays connected."""
    alice.start_websocket(
        socket_open_callback=lambda: logging.info("✅ WebSocket Connected"),
        socket_close_callback=lambda: logging.warning("⚠️ WebSocket Closed. Reconnecting..."),
        socket_error_callback=lambda msg: logging.error(f"❌ WebSocket Error: {msg}"),
        subscription_callback=feed_data,
        run_in_background=True,
        market_depth=False
    )

# ----------------------------------------------------------------
# ✅ FUNCTION: Collect Market Data (9:15 - 9:25 AM)
# ----------------------------------------------------------------
def collect_market_data():
    """Subscribe & collect market data from 9:15 AM to 9:25 AM."""
    logging.info("🔄 Starting Market Data Collection (9:15 AM - 9:25 AM)...")

    reconnect_websocket()  # ✅ Start WebSocket

    # ✅ Subscribe to all stock tokens before collecting data
    stock_tokens = INSTRUMENT_TOKENS  
    subscribe_list = [alice.get_instrument_by_token('NSE', token) for token in stock_tokens]
    alice.subscribe(subscribe_list)

    logging.info(f"✅ Subscribed to {len(stock_tokens)} Stock Tokens")

    # ✅ Collect Market Data for 10 Minutes
    while datetime.now() < end_time:
        time.sleep(1)

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

# ----------------------------------------------------------------
# ✅ FUNCTION: Get Top Losers & ATM Options
# ----------------------------------------------------------------
def get_top_losers_fnc():
    """Identify top losers, unsubscribe unnecessary tokens & fetch ATM options."""
    
    logging.info("🔍 Identifying Top Losers...")
    
    # ✅ Read & sort summary data
    df = pd.read_csv(SUMMARY_DATA_FILE)
    df_sorted = df.sort_values(by="percentage_change")
    df_top_loser = df_sorted.head(TOP_LOSSER_COUNT)

    logging.info(f"Top {TOP_LOSSER_COUNT} Losers:\n{df_top_loser}")

    # ✅ Unsubscribe from other tokens
    top_loser_tokens = df_top_loser["token"].tolist()
    tokens_to_unsubscribe = [token for token in INSTRUMENT_TOKENS if token not in top_loser_tokens]
    
    # ✅ Unsubscribe (Uncomment when using real API)
    unsubscribe_list = [alice.get_instrument_by_token('NSE', token) for token in tokens_to_unsubscribe]
    alice.unsubscribe(unsubscribe_list)

    logging.info(f"📉 Unsubscribed from {len(tokens_to_unsubscribe)} non-loser stocks.")

    # ✅ Merge with NSE Data
    top_loser_df = df_top_loser.merge(nse_df, how='left', right_on='Token', left_on='token')

    # ✅ Fetch NFO Contract Data
    nfo_contract_df = fetch_nfo_contract_data()

    if nfo_contract_df is None or nfo_contract_df.empty:
        logging.error("❌ No NFO data found! Returning top losers without options.")
        return top_loser_df

    # ✅ Merge Top Losers with ATM Strike Options
    merged_data = []
    
    for _, row in top_loser_df.iterrows():
        symbol, close_price_stock = row['Symbol'], row['close']

        # ✅ Filter for ATM PUT options (expiring in FEB)
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

    df_merged_nse_nfo.to_csv("nsodata.csv", index=False)
     
    logging.info("✅ Merged Top Losers with ATM Options.")
    return df_merged_nse_nfo

# ----------------------------------------------------------------
# ✅ FUNCTION: Run Live Trading
# ----------------------------------------------------------------
 

def run_live_trading(df_top_losers):
    """Subscribe to FNO options using `get_instrument_for_fno()` for top losers."""
    logging.info("✅ Starting Live Trading...")

    # ✅ Ensure required columns exist
    required_columns = {"symbol", "expiry_date", "strike_price"}
    missing_columns = required_columns - set(df_top_losers.columns)
    if missing_columns:
        logging.error(f"❌ Missing required columns: {missing_columns}")
        return

    subscribe_list = []

    # ✅ Subscribe to FNO Option Contracts
    for _, row in df_top_losers.iterrows():
        

        symbol = row["symbol"]
        strike = row["strike_price"]
        expiry = row["expiry_date"]

        try:
            # ✅ Convert expiry_date from Unix timestamp to a readable format
            if isinstance(expiry, (int, float)):  # If expiry is in timestamp format
                expiry_date = datetime.utcfromtimestamp(expiry / 1000).strftime("%Y-%m-%d")
            else:
                expiry_date = str(expiry)  # Convert string expiry directly

            expiry_date_obj = datetime.strptime(expiry_date, "%Y-%m-%d")  # Convert to datetime object

            # ✅ Fetch FNO Option Instrument
            option_contract = alice.get_instrument_for_fno(
                symbol=symbol,
                expiry_date=expiry_date,
                is_fut=False,
                strike=int(strike),
                exch = 'NFO',
                is_CE=False  # ✅ Change to True for Call Options
            )

            if option_contract:
                subscribe_list.append(option_contract)
            else:
                logging.warning(f"⚠️ No FNO contract found for {symbol} {strike} {expiry_date}")

        except Exception as e:
            logging.error(f"❌ Error fetching FNO instrument for {symbol} {strike}: {e}")

    if not subscribe_list:
        logging.error("❌ No valid FNO instruments to subscribe to! Aborting subscription.")
        return

    # ✅ Save subscribed tokens to a file
    with open(SUBSCRIBED_TOKENS_FILE, "w") as file:
        file.write("Subscribed Tokens:\n")
        file.write("\n".join([str(instr.token) for instr in subscribe_list]))

    logging.info(f"✅ Subscribing to {len(subscribe_list)} FNO instruments.")
    alice.subscribe(subscribe_list)

    # stock_tokens = df_top_losers["token"].tolist()
    # subscribe_list = [alice.get_instrument_by_token('NSE', token) for token in stock_tokens]
    # alice.subscribe(subscribe_list)
    # logging.info(f"✅ Subscribed to {len(stock_tokens)} Stock Tokens")

    
    reconnect_websocket()  # Start WebSocket for live monitoring


    while True:
        time.sleep(1)

# ----------------------------------------------------------------
# ✅ EXECUTE BOT
# ----------------------------------------------------------------
collect_market_data()  # Phase 1: Collect Data
top_losers_df = get_top_losers_fnc()  # Phase 2 
 

run_live_trading(top_losers_df)  # Phase 3: Live Trading on Top Losers
