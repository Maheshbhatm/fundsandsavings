import logging
from datetime import datetime
import sqlite3
from algo_lib import *  
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
import time as pytime  

CURRENT_DATE = datetime.today().strftime('%Y-%m-%d')

PATH = f"algo_trading/files/"
SESSION_FILE = PATH + "SESSION_FILE.txt"
TICK_DATA_FILE = PATH + f"tick_stock_data_{CURRENT_DATE}.txt"
SUMMARY_DATA_FILE = PATH + f"summary_stock_data_{CURRENT_DATE}.csv" 
TOP_COMBINED_DATA_FILE = PATH + f"stock_final_data_{CURRENT_DATE}.csv" 
DB_FILE = "ticks_data.db"

INSTRUMENT_TOKENS = [17903,3103,21690,10999,10738,11532,16669,13,13751,1964,3150,157,11543,317,881,9590,11703,17818,10940,547,1348,18564,18365,910,11195,4244,312,3363,24184,2303,19585,11536,19913,1901,11483,15141,3518,3506,4306,2664,236,4503,335,17875,2031,25,8479,2885,1394,1232,17963,3273,10440,21770,16713,20242,23650,3351,1594,7229,3718,9819,1922,16675,20302,1333,21808,13538,10604,3563,6656,739,694,10447,275,685,422,15083,10099,5258,4963,5900,3220,10217,7929,3432,11723,22377,9480,6733,3456,13611,14732,3045,18652,467,6705,1363,17971,6066,2955,17869,4067,1512,18921,772,1270,3787,404,17438,15355,1660,3063,20374,14299,3426,11630,1406,29135,11351,526,14977,18143,383,2475,5097,4668,438,15332,212,4717,4204,1624,3499,2029,10753,10794,10666,17400,11915,14366]
BUDGET = 4000
TOP_LOSERS_COUNT = 2
TOP_GAINER_COUNT = 0
LOSERS_PECENTAGE_CHANGE = -0.2
GAINERS_PECENTAGE_CHANGE = 0.2

STOPLOSS_PECENTAGE = 1 / 100
MARGIN = 1
NSE_DF = pd.read_csv(PATH + "NSE.csv")

start_time = datetime.now()
end_time = start_time.replace(hour=11, minute=00, second=0, microsecond=0)  

# ✅ Read session details
try:
    with open(SESSION_FILE, "r") as f:
        session_data = json.load(f)
        session_id = session_data.get("session_id")
except FileNotFoundError:
    logging.error("❌ AliceBlue session file not found. Ensure live_data_v1.py is running.")
    exit(1)

config = read_config("aliceblue/alice_blue_config.txt") 
USER_ID = config.get("USER_ID")
API_KEY = config.get("API_KEY")
ENCKEY = config.get("ENCKEY")
SESSION_TOKEN = get_bearer_token()
BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
TRADE_BOOK = "/placeOrder/fetchTradeBook"
ORDER_BOOK = "/placeOrder/fetchOrderBook"
POSITION_BOOK = "/positionAndHoldings/positionBook"

trade_book_url = BASE_URL + TRADE_BOOK
order_book_url = BASE_URL + ORDER_BOOK
position_book_url = BASE_URL + ORDER_BOOK

# ✅ Reconnect to AliceBlue using session_id
alice = Aliceblue(user_id=USER_ID, api_key=API_KEY, session_id=session_id)

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

def get_trade_result(url): 
    headers = {
        "Authorization": SESSION_TOKEN,
        "Content-Type": "application/json"
    } 
    response = requests.get(url, headers=headers) 
    if response.status_code == 200:
        data = response.json()  
        
        df = pd.DataFrame()
        if isinstance(data, dict) and data.get('stat') == 'Not_Ok':
            print("No Data Available")
            return df
        else:
            df = pd.DataFrame(data)
            return df
    else:
        print(f"Failed to fetch data: {response.status_code} - {response.text}")

def process_tick_data(DB_FILE):
    """Process collected tick data and compute stock movements."""
    logging.info("Processing Tick Data from DB...")
    try: 
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT token, high, low, open, close, created_at, ft FROM ticks"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            logging.error("No tick data available in DB for processing.")
            return None 
        
        df["token"] = df["token"].astype(str)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df["ft"] = pd.to_numeric(df["ft"], errors="coerce") 
        df.set_index("created_at", inplace=True) 
        return df

    except Exception as e:
        logging.error(f"❌ Error processing tick data from DB: {e}")
        return None
     
def get_summary(df):
    summary = df.groupby('token').agg(
            open_price=('open', 'first'),
            close_price=('close', 'last'),
            high=('high', 'max'),
            low=('low', 'min')
        ).reset_index()

    summary['gap'] = summary['close_price'] - summary['open_price']
    summary['percentage_change'] = (summary['gap'] / summary['open_price']) * 100
    summary['label'] = summary['percentage_change'].apply(lambda x: 'gainer' if x > 0 else 'loser')

    summary.rename(columns={ 'open_price': 'open', 'close_price': 'close'}, inplace=True)
    summary.to_csv(SUMMARY_DATA_FILE, index=False) 
         
    return df

def get_top_losers():
    logging.info("🔍 Identifying Top Losers...") 
    df = pd.read_csv(SUMMARY_DATA_FILE)

    df_sorted = df.sort_values(by="percentage_change")
    df_sorted = df_sorted[(df_sorted["percentage_change"] <= LOSERS_PECENTAGE_CHANGE) | (df_sorted["percentage_change"] >= GAINERS_PECENTAGE_CHANGE)]

    top_loosers_df = df_sorted.head(TOP_LOSERS_COUNT)
    top_gainer_df = df_sorted.tail(TOP_GAINER_COUNT)

    top_combined_df = pd.concat([top_loosers_df, top_gainer_df])
 
    top_combined_df["trade_executed"] = pd.Series([None] * len(top_combined_df), dtype="object")
    top_combined_df["target_order"] = pd.Series([None] * len(top_combined_df), dtype="object")
    top_combined_df["stoploss_order"] = pd.Series([None] * len(top_combined_df), dtype="object") 

    # logging.info(f"Top Combined DF :\n{top_combined_df}")

    # WORK ON THIS LATER TO UN SUBSCRIBE 
    # if len(top_combined_df) >= 0:
    #     top_loser_tokens = top_combined_df["token"].tolist()
    #     tokens_to_unsubscribe = [token for token in INSTRUMENT_TOKENS if token not in top_loser_tokens]
    #     unsubscribe_list = [alice.get_instrument_by_token('NSE', token) for token in tokens_to_unsubscribe]
    #     alice.unsubscribe(unsubscribe_list)
    # logging.info(f"📉 Unsubscribed from {len(tokens_to_unsubscribe)} non-loser stocks.")

    top_combined_df = top_combined_df.merge(NSE_DF, how='left', right_on='Token', left_on='token')
    if not os.path.exists(TOP_COMBINED_DATA_FILE):
        print(" The file is not exist, created a new file. ")
        top_combined_df.to_csv(TOP_COMBINED_DATA_FILE, index=False)
    logging.info("✅ Merged Dataframe.")
    
    return top_combined_df


print( " START " )
tick_df = process_tick_data(DB_FILE)
gainers_loosers_df = get_summary(tick_df)

if datetime.now() <= end_time:
    logging.info(f"✅ {datetime.now()}  <= {end_time} ")
     
if datetime.now() > end_time:

    
    top_combined_df = get_top_losers()
    logging.info(f"✅ {datetime.now()}  > {end_time} ")  

    while True:
        # Executing for loser  
        top_combined_df = pd.read_csv(TOP_COMBINED_DATA_FILE)
        logging.info(f"Top DF :\n{top_combined_df[['Symbol','Token','Trading Symbol', 'label', 'trade_executed' , 'target_order', 'stoploss_order']]}")
        for index, loser in top_combined_df.iterrows():  
            trading_symbol = loser['Trading Symbol']
            if loser['label']  == "loser" :  

                position_book_df = get_trade_result(position_book_url)
                if position_book_df.empty:
                    print(" No Open Positions ")
                else: 
                    position_book_df = position_book_df[position_book_df['Status'] == 'complete'] 
                    position_book_df.to_csv("/Users/mahesh/Downloads/position_book_df.csv")

                    if trading_symbol in position_book_df['Trsym'].values:
                        top_combined_df.at[index, "trade_executed"] = "YES"
                        top_combined_df.to_csv(TOP_COMBINED_DATA_FILE, index=False)

                    if loser['trade_executed'] == "YES" and loser['stoploss_order'] !=  "YES":
                            match = position_book_df[position_book_df['Trsym'] == trading_symbol]

                            if not match.empty:
                                AvgPrice = float(match['Avgprc'].iloc[0] )
                                quantity = match['Qty'].iloc[0]  

                            print( f"✅ AvgPrice : {AvgPrice} |  bqty : {quantity} ")
                            transtype = 'BUY'
                            exch = 'NSE'
                            stock_token = loser['Token'] 
                            tick_size =  float (loser['Tick Size'])

                            stock_price_stoploss_change = AvgPrice * STOPLOSS_PECENTAGE
                            raw_option_stoploss_price = AvgPrice + stock_price_stoploss_change
                            stoploss_price = round(float(raw_option_stoploss_price) / tick_size) * tick_size

                            message = f"""✅ STOPLOSS  \n SYMBOL : {trading_symbol} \n PRICE {stoploss_price} \n transtype = {transtype} \n exch = {exch} \n symbol_id = {trading_symbol} \n quantity = {quantity} """
                            # order_response = place_stoploss_order(transtype, exch, stock_token, trading_symbol, quantity, stoploss_price, stoploss_price)
                            # print(f"✅ {order_response}")

                            top_combined_df.at[index, "stoploss_order"] = "YES"
                            top_combined_df.to_csv(TOP_COMBINED_DATA_FILE, index=False)

                if loser['trade_executed'] != "YES" and loser['label']  == "loser" :  
                    latest_data = tick_df[tick_df['token'] == str( loser['Token']  ) ] 
    
                    latest_price = latest_data['close'].dropna().iloc[-1] # Get latest price

                    stock_token = loser['Token'] 
                    low_price = loser['low'] 
                    transtype = 'SELL'
                    exch = 'NSE'
                    symbol = loser['Symbol'] 
                    symbol_id = stock_token
                    trading_symbol = loser['Trading Symbol'] 
                    lot_size =  int( loser['Lot Size'])
                    max_lots = BUDGET // (lot_size * ( latest_price / MARGIN ))
                    quantity =  int( loser['Lot Size'] ) * max_lots
                    tick_size =  float (loser['Tick Size'])

                    logging.info(f" Checking for stock_token : {symbol} | low_price {low_price} ")
                    if not latest_data.empty:  
                        print( f"Get latest price {latest_price} < low_price :  {low_price}")   
                        if loser['trade_executed'] != "YES" and latest_price <= low_price:
                            logging.info(f"📉 Low broken for {symbol} at {latest_price}, executing  trade...")
                            print( f""""✅✅✅ The trade has been taken for {trading_symbol} price {latest_price} |
            transtype = {transtype} | symbol_id = {symbol_id} | exch = {exch} |  symbol_id = {symbol_id} | trading_symbol = {trading_symbol} | quantity = {quantity} | max lot = {max_lots} |""")
                                        
                            buy_price = round(float(latest_price) / tick_size * tick_size, 2) 
                            message = f"""✅ SELL TRADE \n SYMBOL : {trading_symbol} \n PRICE {buy_price} \n transtype = {transtype} \n exch = {exch} \n symbol_id = {symbol_id} \n quantity = {quantity} \n max lot = {max_lots} """
                            # send_telegram_alert(message)
                            # top_combined_df.at[index, "trade_executed"] = "YES"

                            top_combined_df.to_csv(TOP_COMBINED_DATA_FILE, index=False)
                            # order_response = place_order(transtype, exch, stock_token, symbol_id, trading_symbol, quantity, buy_price)
                            # print( order_response ) 

                elif loser['trade_executed'] == "YES" and   loser['target_order'] != "YES" :

                        logging.info(f"✅ Checking for traget based on super trend ")
                        tick_df = process_tick_data(DB_FILE)
                        tick_df = tick_df[tick_df['token'] == str( loser['Token'] ) ] 

                        # print("Filtered tick_df shape:", tick_df.shape)
                        # print("Sample rows:\n", tick_df.head())
                        # print("Index dtype:", tick_df.index.dtype)
                        # print("Min and Max time:", tick_df.index.min(), tick_df.index.max()) 

                        ohlc_df = tick_df.groupby("token").resample("5min").agg({
                            "open": "first",
                            "close" : "last",
                            "high": "max",
                            "low": "min" 
                        }).dropna() 
                        ohlc_df = ohlc_df.reset_index()  

                        supertrend_result = ohlc_df.groupby('token', group_keys=False).apply(lambda group: get_supertrend(group['high'], group['low'], group['close'], 1, 1))
                        supertrend_result = supertrend_result.rename(columns={"Strend": "supertrend_value"})
                        ohlc_df["supertrend_value"] = supertrend_result["supertrend_value"] 
                        
                        ohlc_df['supertrend_signal'] = ohlc_df.apply(lambda row: "CLOSE" if row['close'] > row['supertrend_value'] else "OPEN", axis=1)
                        last_row = ohlc_df.iloc[-1]
                        last_supertrend_signal = last_row['supertrend_signal']
                        
                        ohlc_df.to_csv("/Users/mahesh/Downloads/ohlc_df.csv", index=False)
                        print( " Super Trend Signal = ",  last_supertrend_signal)
                        if last_supertrend_signal == 'CLOSE': 
                            
                            stock_token = loser['Token'] 
                            transtype = 'BUY'
                            exch = 'NSE'
                            trading_symbol = loser['Trading Symbol']
                            tick_size =  float (loser['Tick Size'])
                            symbol_id = stock_token
                            lot_size =  int( loser['Lot Size'])  
                            logging.info(f"📊 Super trend reversed for {trading_symbol}, placing order...")
                            latest_data = tick_df[tick_df['token'] == str( stock_token ) ] 
                            latest_price = latest_data['close'].dropna().iloc[-1] 
                            target_price = round(float(latest_price) / tick_size) * tick_size 
                            max_lots = BUDGET // (lot_size * ( latest_price / MARGIN ))
                            quantity =  int( loser['Lot Size'] ) * max_lots 

                            # order_response = place_order('BUY', 'NSE', stock_token, stock_token, trading_symbol, quantity, target_price)
                            top_combined_df.at[index, "target_order"] = "YES"

                            message = f""" 
            📍BUY TRADE
            SYMBOL = {trading_symbol}
            PRICE {target_price}
            transtype = {transtype} 
            exch = {exch}
            symbol_id = {symbol_id}
            quantity = {quantity}
            max lot = {max_lots} """

                            # send_telegram_alert(message)
                            print(message)
                            logging.info(f"✅ Buy order placed at {latest_price}")