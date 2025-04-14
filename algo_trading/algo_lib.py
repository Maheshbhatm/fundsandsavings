import hashlib
import requests
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
import numpy as np
# Read file and get value 

def read_config(file_path):
    config = {}
    with open(file_path, "r") as file:
        for line in file:
            key, value = line.strip().split("=")
            config[key] = value
    return config

# ----------------------------------------------------------------
# ✅ Get Bearer Token 
# ----------------------------------------------------------------
def get_bearer_token():
    BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    api_encp_key_endpoint = "customer/getAPIEncpkey"


    config = read_config("aliceblue/alice_blue_config.txt")

    userId = config.get("USER_ID")
    apiKey = config.get("API_KEY")
    encKey = config.get("ENCKEY")

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
    

def atr(DF,n):
    try:
        "function to calculate True Range and Average True Range"
        df = DF.copy()
        df['H-L']=abs(df['high']-df['low'])
        df['H-PC']=abs(df['high']-df['close'].shift(1))
        df['L-PC']=abs(df['low']-df['close'].shift(1))
        df['TR']=df[['H-L','H-PC','L-PC']].max(axis=1,skipna=False)
        df['ATR'] = df['TR'].ewm(com=n,min_periods=n).mean()
        return df['ATR']
    except Exception as e:
            print(f"atr error: {e}")

def supertrend(DF,n,m):
    try:
        """function to calculate Supertrend given historical candle data
            n = n day ATR - usually 7 day ATR is used
            m = multiplier - usually 2 or 3 is used"""
        df = DF.copy()
        df['ATR'] = atr(df,n)
        df["B-U"]=((df['high']+df['low'])/2) + m*df['ATR'] 
        df["B-L"]=((df['high']+df['low'])/2) - m*df['ATR']
        df["U-B"]=df["B-U"]
        df["L-B"]=df["B-L"]

        ind = df.index
        for i in range(n,len(df)):
            if df['close'][i-1]<=df['U-B'][i-1]:
                df.loc[ind[i],'U-B']=min(df['B-U'][i],df['U-B'][i-1])
            else:
                df.loc[ind[i],'U-B']=df['B-U'][i]    
        for i in range(n,len(df)):
            if df['close'][i-1]>=df['L-B'][i-1]:
                df.loc[ind[i],'L-B']=max(df['B-L'][i],df['L-B'][i-1])
            else:
                df.loc[ind[i],'L-B']=df['B-L'][i]  
        df['Strend']=np.nan
        for test in range(n,len(df)):
            if df['close'][test-1]<=df['U-B'][test-1] and df['close'][test]>df['U-B'][test]:
                df.loc[ind[test],'Strend']=df['L-B'][test]
                break
            if df['close'][test-1]>=df['L-B'][test-1] and df['close'][test]<df['L-B'][test]:
                df.loc[ind[test],'Strend']=df['U-B'][test]
                break
        
        for i in range(n,len(df)):
            
            if df['Strend'][i-1]==df['U-B'][i-1] and df['close'][i]<=df['U-B'][i]:
                df.loc[ind[i],'Strend']=df['U-B'][i]
            elif  df['Strend'][i-1]==df['U-B'][i-1] and df['close'][i]>=df['U-B'][i]:
                df.loc[ind[i],'Strend']=df['L-B'][i]
            elif df['Strend'][i-1]==df['L-B'][i-1] and df['close'][i]>=df['L-B'][i]:
                df.loc[ind[i],'Strend']=df['L-B'][i]
            elif df['Strend'][i-1]==df['L-B'][i-1] and df['close'][i]<=df['L-B'][i]:
                df.loc[ind[i],'Strend']=df['U-B'][i]
        return df[['Strend']] 

    except Exception as e:
            print(f"atr error: {e}")

def send_telegram_alert(message):
    try:
        bot_token = "7690801736:AAE6wgn8loDmMiAo_BUFkde4NDIMZJL-4dM"
        chat_id = "1026628247"  
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Alert sent successfully!")
        else:
            print(f"Failed to send alert: {response.text}")
    except Exception as e:
            print(f"Telegegram error: {e}")

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
 