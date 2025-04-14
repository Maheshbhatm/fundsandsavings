# ----------------------------------------------------------------
# ✅ To Store Live Data into an TXT file
# ----------------------------------------------------------------

import logging
import sys
import os 
from pya3 import Aliceblue
import sqlite3
from datetime import datetime

from algo_lib import * 

# ----------------------------------------------------------------
# ✅ Define all global variables 
# ----------------------------------------------------------------

config = read_config("aliceblue/alice_blue_config.txt") 
USER_ID = config.get("USER_ID")
API_KEY = config.get("API_KEY")
ENCKEY = config.get("ENCKEY") 

CURRENT_DATE = datetime.today().strftime('%Y-%m-%d')
INSTRUMENT_TOKENS = [17903,3103,21690,10999,10738,11532,16669,13,13751,1964,3150,157,11543,317,881,9590,11703,17818,10940,547,1348,18564,18365,910,11195,4244,312,3363,24184,2303,19585,11536,19913,1901,11483,15141,3518,3506,4306,2664,236,4503,335,17875,2031,25,8479,2885,1394,1232,17963,3273,10440,21770,16713,20242,23650,3351,1594,7229,3718,9819,1922,16675,20302,1333,21808,13538,10604,3563,6656,739,694,10447,275,685,422,15083,10099,5258,4963,5900,3220,10217,7929,3432,11723,22377,9480,6733,3456,13611,14732,3045,18652,467,6705,1363,17971,6066,2955,17869,4067,1512,18921,772,1270,3787,404,17438,15355,1660,3063,20374,14299,3426,11630,1406,29135,11351,526,14977,18143,383,2475,5097,4668,438,15332,212,4717,4204,1624,3499,2029,10753,10794,10666,17400,11915,14366]
# INSTRUMENT_TOKENS = [6656] 

SESSION_FILE = f"algo_trading/files/SESSION_FILE.txt"
TICK_DATA_FILE = f"tick_stock_data_{CURRENT_DATE}.txt"
FULL_PATH = f"algo_trading/files/{TICK_DATA_FILE}"
live_prices = {}
 
DB_FILE = "ticks_data.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
# ----------------------------------------------------------------
# ✅ Define Functions
# ----------------------------------------------------------------

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def feed_data(message):
    """Store live tick data directly into SQLite DB."""
    try:
        feed_message = json.loads(message)

        if feed_message.get("t") in ["ck", "tk"]:  # Skip control messages
            return

        token = feed_message.get("tk")
        close = float(feed_message.get("lp", 0))
        high = float(feed_message.get("h", feed_message.get("lp", 0)))
        low = float(feed_message.get("l", feed_message.get("lp", 0)))
        open_price  = float(feed_message.get("ap", feed_message.get("lp", 0)))  # avg price or lp
        
        ft = feed_message.get("ft")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not token or not close:
            return

        cursor.execute("""
            INSERT INTO ticks (token, high, low, open, close, created_at, ft)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (token, high, low, open_price , close, created_at, ft))
        conn.commit()

        with open(FULL_PATH, "a") as file:
            file.write(json.dumps(feed_message) + "\n")

        cursor.execute("SELECT COUNT(*) FROM ticks")
        row_count = cursor.fetchone()[0]
        print(f"Total rows: {row_count}")
        
        logging.info(f"📥 Tick saved to DB: {token} @ {close}")

    except Exception as e:
        logging.error(f"❌ Error in feed_data: {e}")

def feed_data_(message):
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

            # ✅ Add created_at field to the JSON
            feed_message["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ✅ Save tick data in file for post 9:25 AM processing
            tick_data = json.dumps(feed_message) + "\n"
            with open(FULL_PATH, "a") as file:
                file.write(tick_data)

            logging.info(f"📝 Tick Data Stored: {tick_data.strip()}")

    except Exception as e:
        logging.error(f"❌ Error in feed_data: {e}")


def reconnect_websocket():
    """Ensures WebSocket stays connected."""
    global websocket_connected

    def on_open():
        global websocket_connected
        websocket_connected = True
        logging.info("✅ WebSocket Connected")

    def on_close():
        global websocket_connected
        websocket_connected = False
        logging.warning("⚠️ WebSocket Closed. Reconnecting...")

    def on_error(msg):
        global websocket_connected
        websocket_connected = False
        logging.error(f"❌ WebSocket Error: {msg}")

    alice.start_websocket(
        socket_open_callback=on_open,
        socket_close_callback=on_close,
        socket_error_callback=on_error,
        subscription_callback=feed_data,
        run_in_background=True,
        market_depth=False
    )

    # Wait briefly to allow connection check
    time.sleep(2)
    if websocket_connected:
        logging.info("✅ WebSocket is successfully connected!")
    else:
        logging.warning("⚠️ WebSocket failed to connect, will retry...")

def create_session( ):
    # ✅ Initialize AliceBlue API session
    try:    
        alice = Aliceblue(user_id=USER_ID, api_key=API_KEY)
        session_id = alice.get_session_id()
        logging.info("✅ AliceBlue API Session Initialized Successfully")  

        with open(SESSION_FILE, "w") as f:
            json.dump({"session_id": session_id}, f)
        
        logging.info("✅ AliceBlue API Session Initialized Successfully")  

        return alice
    except Exception as e:
        logging.error(f"❌ API Authentication Failed: {e}")
        sys.exit(1)
     
def collect_market_data():
    logging.info("🔄 Starting Market Data Collection ")

    reconnect_websocket() 

    stock_tokens = INSTRUMENT_TOKENS  
    subscribe_list = []
    for token in stock_tokens:
        try:
            instrument = alice.get_instrument_by_token('NSE', token)
            subscribe_list.append(instrument)
        except Exception as e:
            print(f"Skipping token {token} due to error: {e}")

    alice.subscribe(subscribe_list)

    logging.info(f"✅ Subscribxed to {len(stock_tokens)} Stock Tokens")

    if not os.path.exists(FULL_PATH):
        with open(FULL_PATH, 'w') as file:
            pass   

    while True:    
        pass 

# ----------------------------------------------------------------
# ✅ Calling Functions
# ----------------------------------------------------------------

def main():
    global alice 
    alice = create_session()
    collect_market_data()

if __name__ == "__main__":
    main()