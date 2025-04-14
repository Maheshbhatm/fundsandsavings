import logging
import pandas as pd 
import json 
import time as pytime   
from datetime import datetime, time 

import numpy as np 

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

CURRENT_DATE = datetime.today().strftime('%Y-%m-%d')

PATH = f"algo_trading/files/" 
TICK_DATA_FILE = PATH + f"tick_stock_data_2025-04-11.txt"


def date_to_unix_timestamp(date_str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    timestamp_ms = round(time.mktime(date_obj.timetuple()) * 1000)
    return timestamp_ms

def get_supertrend(high, low, close, lookback, multiplier):
    
    # ATR
    
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis = 1, join = 'inner').max(axis = 1)
    atr = tr.ewm(lookback).mean()
    
    # H/L AVG AND BASIC UPPER & LOWER BAND
    
    hl_avg = (high + low) / 2
    upper_band = (hl_avg + multiplier * atr).dropna()
    lower_band = (hl_avg - multiplier * atr).dropna()
    
    # FINAL UPPER BAND    
    final_bands = pd.DataFrame(columns = ['upper', 'lower'])
    final_bands.iloc[:,0] = [x for x in upper_band - upper_band]
    final_bands.iloc[:,1] = final_bands.iloc[:,0]    
    for i in range(len(final_bands)):
        if i == 0:
            final_bands.iloc[i,0] = 0
        else:
            if (upper_band[i] < final_bands.iloc[i-1,0]) | (close[i-1] > final_bands.iloc[i-1,0]):
                final_bands.iloc[i,0] = upper_band[i]
            else:
                final_bands.iloc[i,0] = final_bands.iloc[i-1,0]
    
    # FINAL LOWER BAND
    
    for i in range(len(final_bands)):
        if i == 0:
            final_bands.iloc[i, 1] = 0
        else:
            if (lower_band[i] > final_bands.iloc[i-1,1]) | (close[i-1] < final_bands.iloc[i-1,1]):
                final_bands.iloc[i,1] = lower_band[i]
            else:
                final_bands.iloc[i,1] = final_bands.iloc[i-1,1]
    
    # SUPERTREND
    
    supertrend = pd.DataFrame(columns = [f'supertrend_{lookback}'])
    supertrend.iloc[:,0] = [x for x in final_bands['upper'] - final_bands['upper']]
    
    for i in range(len(supertrend)):
        if i == 0:
            supertrend.iloc[i, 0] = 0
        elif supertrend.iloc[i-1, 0] == final_bands.iloc[i-1, 0] and close[i] < final_bands.iloc[i, 0]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 0]
        elif supertrend.iloc[i-1, 0] == final_bands.iloc[i-1, 0] and close[i] > final_bands.iloc[i, 0]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 1]
        elif supertrend.iloc[i-1, 0] == final_bands.iloc[i-1, 1] and close[i] > final_bands.iloc[i, 1]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 1]
        elif supertrend.iloc[i-1, 0] == final_bands.iloc[i-1, 1] and close[i] < final_bands.iloc[i, 1]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 0]
    
    supertrend = supertrend.set_index(upper_band.index)
    
    # ST UPTREND/DOWNTREND
    
    upt = []
    dt = []
    close = close.iloc[len(close) - len(supertrend):]

    for i in range(len(supertrend)):
        if close[i] > supertrend.iloc[i, 0]:
            upt.append(supertrend.iloc[i, 0])
            dt.append(np.nan)
        elif close[i] < supertrend.iloc[i, 0]:
            upt.append(np.nan)
            dt.append(supertrend.iloc[i, 0])
        else:
            upt.append(np.nan)
            dt.append(np.nan)
            
    st, upt, dt = pd.Series(supertrend.iloc[:, 0]), pd.Series(upt), pd.Series(dt)
    upt.index, dt.index = supertrend.index, supertrend.index
    
    return st, upt, dt
 
import json
import logging
import pandas as pd

def process_tick_data(TICK_DATA_FILE):
    """Process collected tick data and compute stock movements."""
    logging.info("Processing Tick Data...")
    try:
        with open(TICK_DATA_FILE, "r") as file:
            data = [json.loads(line.strip()) for line in file if line.strip()]
        if not data:
            logging.error("No tick data available for processing.")
            return None
        df = pd.DataFrame(data)
        for col in ["h", "l", "ap"]:
            df[col] = df[col].fillna(df["lp"]) if col in df.columns else df["lp"] 
        all_columns = ["created_at", "t", "e", "tk", "lp", "pc", "ft", "h", "l", "ap", "v", "bp1", "sp1", "bq1", "sq1"]
        df = df.reindex(columns=all_columns, fill_value="")
        numeric_columns = ["lp", "pc", "ft", "h", "l", "ap", "v", "bp1", "sp1", "bq1", "sq1"]
        df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
        df['created_at'] = df['ft'].apply(lambda x: pytime.strftime('%Y-%m-%d %H:%M:%S', pytime.localtime(x)))  
        df['created_at'] = pd.to_datetime(df['created_at'], format='%Y-%m-%d %H:%M:%S') 
        df.set_index('created_at', inplace=True)  
        return df

    except Exception as e:
        logging.error(f"❌ Error processing tick data: {e}")
        return None


tick_df = process_tick_data(TICK_DATA_FILE) 
tick_df = tick_df[tick_df['tk'] == str( 13 )]  

cutoff_time = datetime.strptime('09:15:00', '%H:%M:%S').time()
mask = tick_df.index.time < cutoff_time

new_index = tick_df.index.where(
    ~mask,
    tick_df.index.normalize() + pd.Timedelta(hours=9, minutes=15)
)

tick_df.index = new_index
tick_df_adjusted = tick_df.sort_index()

ohlc_df = tick_df_adjusted.groupby("tk").resample("5min").agg({
                        "lp": ["first", "last"],
                        "h": "max",
                        "l": "min",
                        "v": "sum"
                    }).dropna() 

ohlc_df.columns = ['open','close',  'high', 'low',   'price_change']
ohlc_df = ohlc_df.reset_index()  
 

ohlc_df['st'], ohlc_df['s_upt'], ohlc_df['st_dt'] = get_supertrend(ohlc_df['high'], ohlc_df['low'], ohlc_df['close'], 1, 1)
tsla = ohlc_df[1:]
tsla['signal'] = None
tsla.loc[tsla['s_upt'].notna(), 'signal'] = 'green' 
tsla.loc[tsla['st_dt'].notna(), 'signal'] = 'red'
print( tsla )
 