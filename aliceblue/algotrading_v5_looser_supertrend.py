import json
import time
import logging
import pandas as pd
import requests
from datetime import datetime
from pya3 import Aliceblue
import sys
import hashlib
import signal
import os 
from alice_blue import *
from algo_lib import * 

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ API Credentials
config = read_config("aliceblue/alice_blue_config.txt")
USER_ID = config.get("USER_ID")
API_KEY = config.get("API_KEY")
ENCKEY = config.get("ENCKEY")

SESSION_TOKEN = get_bearer_token()

# ✅ Initialize AliceBlue API session
try:    
    alice = Aliceblue(user_id=USER_ID, api_key=API_KEY)
    alice.get_session_id()
    logging.info("✅ AliceBlue API Session Initialized Successfully")  
except Exception as e:
    logging.error(f"❌ API Authentication Failed: {e}")
    sys.exit(1)
     
# ✅ Current Date
current_date = datetime.today().strftime('%Y-%m-%d')

# ✅ Constants
INSTRUMENT_TOKENS = [17903,3103,21690,10999,10738,11532,16669,13,13751,1964,3150,157,11543,317,881,9590,11703,17818,10940,547,1348,18564,18365,910,11195,4244,312,3363,24184,2303,19585,11536,19913,1901,11483,15141,3518,3506,4306,2664,236,4503,335,17875,2031,25,8479,2885,1394,1232,17963,3273,10440,21770,16713,20242,23650,3351,1594,7229,3718,9819,1922,16675,20302,1333,21808,13538,10604,3563,6656,739,694,10447,275,685,422,15083,10099,5258,4963,5900,3220,10217,7929,3432,11723,22377,9480,6733,3456,13611,14732,3045,18652,467,6705,1363,17971,6066,2955,17869,4067,1512,18921,772,1270,3787,404,17438,15355,1660,3063,20374,14299,3426,11630,1406,29135,11351,526,14977,18143,383,2475,5097,4668,438,15332,212,4717,4204,1624,3499,2029,10753,10794,10666,17400,11915,14366]
# INSTRUMENT_TOKENS = [4306]
TICK_DATA_FILE = f"tick_stock_data_{current_date}.txt"
SUMMARY_DATA_FILE = f"summary_stock_data__{current_date}.txt" 
FNO_SUBSCRIPTION_FILE = f"fno_stock_subscription_log__{current_date}.txt"
TOP_LOSSER_COUNT = 2
BUDGET = 5000
PECENTAGE_CHANGE = -0.8
EXPIRY_MONTH = "MAR"
BASE_URL = "https://api.aliceblueonline.com"
live_prices = {}

# ✅ Read NSE Data
nse_df = pd.read_csv("NSE.csv")

# ✅ Track Execution Time
start_time = datetime.now()
end_time = start_time.replace(hour=9, minute=21, second=0, microsecond=0)  

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

# def reconnect_websocket():
#     """Ensures WebSocket stays connected."""
#     alice.start_websocket(
#         socket_open_callback=lambda: logging.info("✅ WebSocket Connected"),
#         socket_close_callback=lambda: logging.warning("⚠️ WebSocket Closed. Reconnecting..."),
#         socket_error_callback=lambda msg: logging.error(f"❌ WebSocket Error: {msg}"),
#         subscription_callback=feed_data,
#         run_in_background=True,
#         market_depth=False
#     )

websocket_connected = False  # Global flag to track WebSocket status

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
# ----------------------------------------------------------------
# ✅ FUNCTION: TRADE - STOPLOSS
# ----------------------------------------------------------------
def place_stoploss_order(transtype, exch, symbol_id, trading_symbol, quantity, stoploss_price, trigger_price):
    
    url = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder"
    payload = json.dumps([
        {
            "complexty": "regular",
            "discqty": "0",
            "exch": exch,
            "pCode": "mis",
            "prctyp": "SL",
            "price": str(stoploss_price),
            "trigPrice": str(stoploss_price),
            "qty": int(quantity),
            "ret": "DAY",
            "symbol_id": symbol_id,
            "trading_symbol": trading_symbol,
            "transtype": transtype,
            "orderTag": "stoploss_order",
            "deviceNumber": "sdagds345324dsfgfvasdqwr4"
        }
    ])
    headers = {
        'Content-Type': 'application/json',
        'Authorization': SESSION_TOKEN
    }
    response = requests.post(url, headers=headers, data=payload)
    return response.text

def place_order(transtype, exch, token, symbol_id, trading_symbol, quantity, price):
    try:
        url = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/placeOrder/executePlaceOrder"
        payload = json.dumps([
            {
                "complexty": "regular",
                "discqty": "0",
                "exch": exch,
                "pCode": "mis",
                "prctyp": "L",
                "price": str(price),
                "trigPrice": "",
                "qty": int(quantity),
                "ret": "DAY",
                "symbol_id": symbol_id,
                "trading_symbol": trading_symbol,
                "transtype": transtype,
                "orderTag": "place_order",
                "deviceNumber": "sdagds345324dsfgfvasdqwr4"
            }
        ])
        headers = {
            'Content-Type': 'application/json',
            'Authorization': SESSION_TOKEN
        }
        response = requests.post(url, headers=headers, data=payload)
        return response.text
    except Exception as e:
                logging.error(f"❌ place_order {e}")

# ----------------------------------------------------------------
# ✅ FUNCTION: Collect Market Data (9:15 - 9:25 AM)
# ----------------------------------------------------------------
def collect_market_data():
    logging.info("🔄 Starting Market Data Collection (9:15 AM - 9:20 AM)...")
    reconnect_websocket() 

    # ✅ Subscribe to all stock tokens before collecting data
    stock_tokens = INSTRUMENT_TOKENS  
    subscribe_list = []
    for token in stock_tokens:
        try:
            instrument = alice.get_instrument_by_token('NSE', token)
            subscribe_list.append(instrument)
        except Exception as e:
            print(f"Skipping token {token} due to error: {e}")

    alice.subscribe(subscribe_list)
    logging.info(f"✅ Subscribed to {len(stock_tokens)} Stock Tokens")

    if not os.path.exists(TICK_DATA_FILE):
        with open(TICK_DATA_FILE, 'w') as file:
            pass   
    top_loser_check = False
    
    while True:     
        all_tick_data_df = process_tick_data() 
        
        if top_loser_check == False and  datetime.now() > end_time:    
            top_loser_check = True
            top_losers_df = get_top_losers()
            top_losers_df["trade_executed"] = ""
            top_losers_df["target_executed"] = ""
        elif top_loser_check and len(top_losers_df)>0  :
            top_losers_df.to_csv("top_losers_df.csv", index=False)
            try:        
                for index, loser in top_losers_df.iterrows():    
                    if  loser['trade_executed'] != "YES":
                        
                        latest_data = all_tick_data_df[all_tick_data_df['tk'] == str( loser['Token']  ) ] 
                        latest_price = latest_data['lp'].dropna().iloc[-1] # Get latest price

                        stock_token = loser['Token'] 
                        low_price = loser['low'] 
                        transtype = 'SELL'
                        exch = 'NSE'
                        symbol_id = stock_token
                        trading_symbol = loser['Trading Symbol'] 
                        lot_size =  int( loser['Lot Size'])
                        max_lots = BUDGET // (lot_size * ( latest_price / 4.5 ))
                        quantity =  int( loser['Lot Size'] ) * max_lots
                        tick_size =  float (loser['Tick Size'])
                        
                        print( f" Checking for stock_token : {stock_token} | low_price {low_price} ")
                        if not latest_data.empty:
                            
                            print( f"Get latest price {latest_price} < low_price :  {low_price}")
            
                            # Check if low is broken
                            if loser['trade_executed'] != "YES" and latest_price <= low_price:
                                logging.info(f"📉 Low broken for {stock_token} at {latest_price}, executing  trade...")
                                print( f""""✅✅✅ The trade has been taken for {trading_symbol} price {latest_price} |
    transtype = {transtype} | symbol_id = {symbol_id} | exch = {exch} |  symbol_id = {symbol_id} | trading_symbol = {trading_symbol} | quantity = {quantity} | max lot = {max_lots} |""")
                                    
                                buy_price = round(float(latest_price) / tick_size * tick_size, 2) 

                                message = f"""✅ SELL TRADE \n SYMBOL : {trading_symbol} \n PRICE {buy_price} \n transtype = {transtype} \n exch = {exch} \n symbol_id = {symbol_id} \n quantity = {quantity} \n max lot = {max_lots} """
                                send_telegram_alert(message)

                                top_losers_df.at[index, "trade_executed"] = "YES"
                                order_response = place_order(transtype, exch, stock_token, symbol_id, trading_symbol, quantity, buy_price)

                                print(f"✅ {order_response}")

                                data = json.loads(order_response)
                                if isinstance(data, list) and data and "stat" in data[0] and data[0]["stat"] == "Ok":
                                    
                                    logging.info(f"✅ Order placed successfully! Order ID: {data[0].get('NOrdNo', 'Unknown')}")
                                    # stoploss_percent = 1.5 / 100  # Convert percentage to decimal
                                    # transtype = 'BUY' 
                                    # order_response = place_stoploss_order(transtype, exch, symbol_id, trading_symbol, quantity, stoploss_price, stoploss_price)
                
                                else:
                                    logging.error("❌ Order placement failed or invalid response.")

                    elif loser['trade_executed'] == "YES" and loser['target_executed'] != "YES":
                        
                            logging.info(f"✅ Checking for traget based on super trend ")
                            df = process_tick_data()   
                            df = df[df['tk'] == str( loser['Token'] ) ] 

                            ohlc_df = df.groupby("tk").resample("5T").agg({
                                "lp": ["first", "last"],  # Open and Close prices
                                "h": "max",  # Highest price in interval
                                "l": "min",  # Lowest price in interval
                                "v": "sum"  # Total volume traded
                            }).dropna()
                            ohlc_df.columns = ['open','close',  'high', 'low',   'price_change']
                            ohlc_df = ohlc_df.reset_index()  

                            ohlc_df['supertrend_value'] = ohlc_df.groupby('tk', group_keys=False).apply(supertrend, n=1, m=1) 

                            ohlc_df['supertrend_signal'] = ohlc_df.apply(lambda row: "CLOSE" if row['close'] > row['supertrend_value'] else "OPEN", axis=1)
                            last_row = ohlc_df.iloc[-1]
                            last_supertrend_signal = last_row['supertrend_signal'] 
                        
                            if last_supertrend_signal == 'CLOSE': 
                                logging.info(f"📊 Super trend reversed for {trading_symbol}, placing order...")

                                latest_data = all_tick_data_df[all_tick_data_df['tk'] == str( stock_token ) ] 
                                latest_price = latest_data['lp'].dropna().iloc[-1] 
                                target_price = round(float(latest_price) / tick_size) * tick_size
                                transtype = 'BUY'
                                exch = 'NSE'
                                trading_symbol = loser['Trading Symbol']
                                order_response = place_order('BUY', 'NSE', stock_token, stock_token, trading_symbol, quantity, target_price)
                                top_losers_df.at[index, "target_executed"] = "YES"

                                message = f""" 
📍BUY TRADE
SYMBOL = {trading_symbol}
PRICE {target_price}
transtype = {transtype} 
exch = {exch}
symbol_id = {symbol_id}
quantity = {quantity}
max lot = {max_lots} """

                                send_telegram_alert(message)
                                
                                logging.info(f"✅ Buy order placed at {latest_price}")
          
                    if datetime.now().hour == 15:
                        pending_orders = top_losers_df[top_losers_df['target_executed'] == "NO"]
                        for _, row in pending_orders.iterrows():

                            latest_data = all_tick_data_df[all_tick_data_df['tk'] == str( stock_token ) ] 
                            latest_price = latest_data['lp'].dropna().iloc[-1] 
                            target_price = round(float(latest_price) / tick_size) * tick_size
                            place_order('BUY', 'NSE', row['Token'], row['Token'], row['Trading Symbol'], quantity, latest_price)
                            logging.info(f"✅ Final order placed for {row['Token']} at {latest_price}")
                            break  
                                
            except Exception as e:
                logging.error(f"❌ PASS {e}")
              
 

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

            dict_data["h"] = dict_data.get("h", dict_data["lp"])
            dict_data["l"] = dict_data.get("l", dict_data["lp"])
            dict_data["ap"] = dict_data.get("ap", dict_data["lp"])

            data.append(dict_data)

        except Exception as e:
            logging.warning(f"Skipping malformed line: {line} | Error: {e}")

    df = pd.DataFrame(data)

    all_columns = ["timestamp", "t", "e", "tk", "lp", "pc", "ft", "h", "l", "ap", "v", "bp1", "sp1", "bq1", "sq1"]
    df = df.reindex(columns=all_columns, fill_value="")
    
    numeric_columns = ["lp", "pc", "ft", "h", "l", "ap", "v", "bp1", "sp1", "bq1", "sq1"]
    df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')

    if df.empty:
        logging.error("No tick data available for processing.")
        return None

    df['timestamp'] = pd.to_datetime(df['timestamp']) 
    df.set_index('timestamp', inplace=True)

    if datetime.now() <= end_time:

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
         
    return df
# ----------------------------------------------------------------
# ✅ FUNCTION: Get Top Losers & ATM Options
# ----------------------------------------------------------------
def get_top_losers():
    """Identify top losers, unsubscribe unnecessary tokens & fetch ATM options."""
    
    logging.info("🔍 Identifying Top Losers...")
    
    # ✅ Read & sort summary data
    df = pd.read_csv(SUMMARY_DATA_FILE)
    df_sorted = df.sort_values(by="percentage_change")
    df_sorted = df_sorted[df_sorted["percentage_change"] <= PECENTAGE_CHANGE]
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

    top_loser_df.to_csv("stock_final_data.csv", index=False)
     
    logging.info("✅ Merged Top Losers with ATM Options.")
    
    return top_loser_df
 
# ----------------------------------------------------------------
# ✅ EXECUTE BOT
# ----------------------------------------------------------------
collect_market_data()  