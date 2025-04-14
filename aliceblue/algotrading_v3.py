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

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ API Credentials
USER_ID = "928693"
API_KEY = "u238MSPxzCEf8yTPe9eb84Q4PofD799tFMOK3pJeRDErtaaMczaVy5V9SZ5FJNHzfM3PYI1vW7C982WpSGhF4paj6yjyLv7bu0Nr9bMaNHZLVjmjeT6FZJXXbSL1HVPI"
ENCKEY = "3OWIVUIJ8MVNK1GJGQ0SERW68MPF90XY"   

def get_bearer_token():
    BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    api_encp_key_endpoint = "customer/getAPIEncpkey"

    userId = USER_ID
    apiKey = API_KEY
    encKey = ENCKEY 

    url = BASE_URL + api_encp_key_endpoint

    data = {
      "userId": userId
    }  
    response = requests.post(url, json=data)
    
    enc_key = ''
    if response.status_code == 200:
        response_json = response.json() 
        enc_key = response_json.get('encKey')

        if enc_key:
            print("encKey:", encKey)
        else:
            print("encKey not found in response")
    else:
        print(f"Failed to get response. Status code: {response.status_code}")
        print("Response Text:", response.text)


    concatenated_string = userId + apiKey + enc_key
    session_id = hashlib.sha256(concatenated_string.encode()).hexdigest()

    get_user_sid_endpoint = "customer/getUserSID"
    url = BASE_URL + get_user_sid_endpoint

    data = {
        "userId": userId,
        "userData": session_id 
    } 
    response = requests.post(url, json=data) 
    
    if response.status_code == 200:
        response_json = response.json()
        sessionID = response_json.get('sessionID') 
    else:
        print(f"Failed to get response. Status code: {response.status_code}")
        print("Response Text:", response.text)

    token_hist = 'Bearer' + ' ' +  userId + ' ' + sessionID

    return token_hist

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
# INSTRUMENT_TOKENS = [ 92813,103902,114338,122309,112787,82329,137099,124738,105965,41340,151611,85233,85689,156638,157086,66588,120798,146683,83104,126929,119640,139580,116844,79579,150497,152953,99859,135005,154840,155560,139300,156062,69811,67065,151127,113485,89018,86730,89559,131708,99952,100231,128726,110908,125144,133947,134503,123950,122611,120356,139389,153556,79135,110601,98123,119154,133147,95790,149111,131251,156224,115254,152397,125618,151015,102673,135293,112856,93956,111785,135827,68168,86175,142343,126865,86055,147531,128390,156926,147711,152787,150073,105046,89132,116072,137500,129557,109458,72394,122579,131367,149731,108848,121482,140358,121247,123012,139682,152493,140166,137601,80099,144662,104281,148229,127419,127637,150639,111251,149949,88169,155862 ]
TICK_DATA_FILE = f"tick_data_{current_date}.txt"
SUMMARY_DATA_FILE = f"summary_data__{current_date}.txt" 
FNO_SUBSCRIPTION_FILE = f"fno_subscription_log.txt"
TOP_LOSSER_COUNT = 5
BUDGET = 40000
EXPIRY_MONTH = "MAR"
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
    """ Subscribe & collect market data from 9:15 AM to 9:25 AM. """
    logging.info("🔄 Starting Market Data Collection (9:15 AM - 9:25 AM)...")
     
    reconnect_websocket() 

    # ✅ Subscribe to all stock tokens before collecting data
    stock_tokens = INSTRUMENT_TOKENS  
    subscribe_list = [alice.get_instrument_by_token('NSE', token) for token in stock_tokens]
    alice.subscribe(subscribe_list)

    logging.info(f"✅ Subscribed to {len(stock_tokens)} Stock Tokens")
    
    if not os.path.exists(TICK_DATA_FILE):
        with open(TICK_DATA_FILE, 'w') as file:
            pass   

    top_loser_check = False
    while True:
        time.sleep(1)

        all_tick_data_df = process_tick_data() 

        top_loser_check == False
        if top_loser_check == False and  datetime.now() > end_time:
            top_loser_check = True
            top_losers_df = get_top_losers_fnc()
            run_live_trading(top_losers_df)

        elif top_loser_check:
            try:
                for _, loser in top_losers_df.iterrows():
                    
                    stock_token = loser['Token']
                    fno_token = loser['token']
                    low_price = loser['low']

                    print( f" Checking for stock_token : {stock_token} | low_price {low_price} and fno_token : {fno_token}")

                    # Find the latest price for this token in all_tick_data_df
                    latest_data = all_tick_data_df[all_tick_data_df['tk'] == str( stock_token ) ] 
                    # print( latest_data.head())
                    if not latest_data.empty:
                        latest_price = latest_data['lp'].dropna().iloc[-1] # Get latest price
                        print( f"Get latest price {latest_price} < low_price :  {low_price}")
                        
                        # Check if low is broken
                        if latest_price < low_price:
                            logging.info(f"📉 Low broken for {fno_token} at {latest_price}, executing ATM trade...")

                            fno_trading_symbol = loser['trading_symbol']
                            
                            all_fno_tick_data_df = get_all_data_fno()
                            fno_latest_data= all_fno_tick_data_df[all_fno_tick_data_df['tk'] == fno_token]

                            print("❌❌ Not empty : ",  fno_latest_data )
                            if not fno_latest_data.empty:
                                print( "fno_latest_data.empty" )
                                fno_latest_price = fno_latest_data['lp'].iloc[-1] 
                                transtype = 'BUY'
                                exch = 'NFO'
                                symbol_id = loser['token']
                                trading_symbol = loser['trading_symbol']
                                lot_size =  int( loser['lot_size'])
                                max_lots = BUDGET // (lot_size * fno_latest_price)
                                quantity =  int( loser['lot_size'] ) * max_lots
                                tick_size =  float (loser['tick_size'])
                                 

                                print( f""""✅✅✅ The trade has been taken for {fno_trading_symbol} price {fno_latest_price} 
transtype = {transtype} | symbol_id = {symbol_id} | exch = {exch} |  symbol_id = {symbol_id} | trading_symbol = {trading_symbol} | quantity = {quantity} | max lot = {max_lots} | fno_latest_price = {fno_latest_price} |""")
                                
                                order_response = place_order(transtype, exch, fno_token, symbol_id, trading_symbol, quantity, fno_latest_price)
                                print(f"✅ {order_response}")
                                data = json.loads(order_response)
                                 
                                # Remove token from tracking to prevent multiple trades
                                top_losers_df = top_losers_df[top_losers_df['token'] != fno_token]

                                # Check if order_response is valid
                                # Check if response is a list and contains expected keys
                                if isinstance(data, list) and len(data) > 0 and "stat" in data[0]:
                                    if data[0]["stat"] == "Ok":
                                        order_id = data[0].get("NOrdNo", "Unknown")
                                        print(f"✅ Order placed successfully! Order ID: {order_id}")
                               
                                        delta = 0.5 
                                        option_target_percent = 0.2 / 100  # Convert percentage to decimal
                                        option_stoploss_percent = 1.5 / 100  # Convert percentage to decimal
                                        underlying_asset_price = low_price
                                        atm_option_premium = fno_latest_price 

                                        # Calculate stock price change for target and stop-loss
                                        stock_price_target_change = underlying_asset_price * option_target_percent
                                        stock_price_stoploss_change = underlying_asset_price * option_stoploss_percent

                                        # Calculate option price change using delta
                                        option_target_change = delta * stock_price_target_change
                                        option_stoploss_change = delta * stock_price_stoploss_change

                                        # Calculate option target and stop-loss percentage
                                        option_target_percentage = (option_target_change / atm_option_premium) * 100
                                        option_stoploss_percentage = (option_stoploss_change / atm_option_premium) * 100

                                        # Calculate raw target and stop-loss prices
                                        raw_option_target_price = atm_option_premium + option_target_change
                                        raw_option_stoploss_price = atm_option_premium - option_stoploss_change
                                        
                                        # Calculate target and stop-loss prices
                                        option_target_price = round(float(raw_option_target_price) / tick_size) * tick_size
                                        option_stoploss_price = round(float(raw_option_stoploss_price) / tick_size) * tick_size


                                        # Print results
                                        print(f"Option Target Percentage: {option_target_percentage:.2f}%")
                                        print(f"Option Stop-Loss Percentage: {option_stoploss_percentage:.2f}%")
                                        print(f"Option Target Price: {option_target_price:.2f}")
                                        print(f"Option Stop-Loss Price: {option_stoploss_price:.2f}") 

                                        transtype = 'SELL' 
                                        order_response = place_order(transtype, exch, fno_token, symbol_id, trading_symbol, quantity, option_target_price)
                                        print(f"✅ {order_response}")

                                        transtype = 'SELL' 
                                        # order_response = place_stoploss_order(transtype, exch, symbol_id, trading_symbol, quantity, option_stoploss_price, option_stoploss_price)
                                        # print(f"✅ {order_response}")
            

                                    else:
                                        print("❌ Order placement failed or invalid response.")
                                else:
                                    print("❌ Unexpected response format from place_order.")



                # Stop monitoring if all tracked stocks have triggered trades
                if top_losers_df.empty:
                    logging.info("✅ All tracked stocks have broken their low. Stopping monitoring.")
                    break 
            except Exception as e:
                logging.error(f"❌ PASS {e}")
             
# ----------------------------------------------------------------
# ✅ FUNCTION: Get All FNO Data
# ----------------------------------------------------------------
def get_all_data_fno():
    """Process collected tick data and compute stock movements."""
    logging.info("Processing FNO Tick Data...")

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
         
    return df

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
def get_top_losers_fnc():
    """Identify top losers, unsubscribe unnecessary tokens & fetch ATM options."""
    
    logging.info("🔍 Identifying Top Losers...")
    
    # ✅ Read & sort summary data
    df = pd.read_csv(SUMMARY_DATA_FILE)
    df_sorted = df.sort_values(by="percentage_change")
    df_sorted = df_sorted[df_sorted["percentage_change"] < -1.8]
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

    print( f" The lenght of nfo_contract_df {len(nfo_contract_df)}")
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
    """Subscribe to FNO options using `get_instrument_for_fno()` for top losers and save the data safely."""
    logging.info("✅ Starting Live Trading...")

    subscribe_list = [] 
    
    # ✅ Open file safely for writing subscription details
    try:
        with open(FNO_SUBSCRIPTION_FILE, "a") as file:
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

                    print(f" Checking for {symbol} - {int(strike)} - {expiry_date}")
                    # ✅ Fetch FNO Option Instrument
                    option_contract = alice.get_instrument_for_fno(
                        symbol=symbol,
                        expiry_date=expiry_date,
                        is_fut=False,
                        strike=int(strike),
                        exch="NFO",
                        is_CE=False  # ✅ Change to True for Call Options if needed
                    )
                    if option_contract:
                        subscribe_list.append(option_contract)
                    else:
                        logging.warning(f"⚠️ No FNO contract found for {symbol} {strike} {expiry_date}")

                except Exception as e:
                    logging.error(f"❌ Error fetching FNO instrument for {symbol} {strike}: {e}")

    except Exception as e:
        logging.error(f"❌ Error opening {FNO_SUBSCRIPTION_FILE} for writing: {e}")
        return

    # ✅ Subscribe to all collected instruments
    if not subscribe_list:
        logging.error("❌ No valid FNO instruments to subscribe to! Aborting subscription.")
        return

    logging.info(f"✅ Subscribing to {len(subscribe_list)} FNO instruments.")
    alice.subscribe(subscribe_list)

# ----------------------------------------------------------------
# ✅ EXECUTE BOT
# ----------------------------------------------------------------
collect_market_data()  