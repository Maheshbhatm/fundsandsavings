import requests
import json
import hashlib
import enum
import logging
import pandas as pd
from datetime import time, datetime
from time import sleep
from collections import namedtuple
import os
import websocket
import threading
from websocket import WebSocketApp

from alice_blue import *

def get_bearer_token():
    BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
    api_encp_key_endpoint = "customer/getAPIEncpkey"

    userId = "928693"   
    apiKey = "EqF9mkSCkRzyMFpGCG9QSEOeTmus6J8OPTEvilpyg8C2OkuVeCGM6fHApSq66dpVhgISIhpnqodmlppKlf1CvudNlJBOA1ycdhmtermzmM9IEidC2ByATqSyU2qEjaBx"  # Replace with your actual API key
    encKey = "3OWIVUIJ8MVNK1GJGQ0SERW68MPF90XY"   

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

    return sessionID

class AliceBlueAPI:
    
    def __init__(self, base_url, user_id):
        self.base_url = base_url
        self.user_id = user_id

    def createSession(self, session_ID):
        url = self.base_url + 'ws/createSocketSess'
        headers = {
            'Authorization': 'Bearer ' + self.user_id + ' ' + session_ID,
            'Content-Type': 'application/json'
        }
        payload = {"loginType": "API"}
        datas = json.dumps(payload)
        response = requests.request("POST", url, headers=headers, data=datas)

        return response.json()
 

base_url = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/"
user_id = "928693"

# Generate a session ID
session_ID = get_bearer_token()

print(session_ID )

alice = AliceBlue(username = "928693", session_id = session_ID)

alice.subscribe(alice.get_instrument_by_symbol('NSE', 'RELIANCE-EQ'), LiveFeedType.TICK_DATA)


# print( alice )

# # Create an instance of the AliceBlueAPI class
# alice_api = AliceBlueAPI(base_url, user_id)

# # Call the createSession method
# response = alice_api.createSession(session_ID)

# # Print the response
# print(response)
 

# def sha256_encryption(value):
#     return hashlib.sha256(value.encode()).hexdigest()

# def get_bearer_token():
#     # Replace with actual implementation to get session_id
#     return get_bearer_token()

# def on_message(ws, message):
#     print("Received:", message)

# def on_error(ws, error):
#     print("Error:", error)

# def on_close(ws, close_status_code, close_msg):
#     print("WebSocket connection closed")

# def on_open(ws):
     
#     client_id = "928693"

#     print(client_id)
#     susertoken = sha256_encryption(sha256_encryption(response))
#     print("Generated susertoken:", susertoken)

#     # Authenticate WebSocket session
#     auth_payload = {
#         "susertoken": susertoken,
#         "t": "c",
#         "actid": client_id + "_API",
#         "uid": client_id + "_API",
#         "source": "API"
#     }
#     ws.send(json.dumps(auth_payload))
#     print("Sent authentication payload:", auth_payload)

#     # Subscribe to market data
#     subscription_payload = {
#         "k": "1594",  # Tokens and exchanges
#         "t": "t"                      # Tick data
#     }
#     ws.send(json.dumps(subscription_payload))
#     print("Sent subscription payload:", subscription_payload)

# websocket_url = "wss://ws1.aliceblueonline.com/NorenWS"

# ws = WebSocketApp(websocket_url,
#                   on_message=on_message,
#                   on_error=on_error,
#                   on_close=on_close)

# ws.on_open = on_open
# ws.run_forever()


# def event_handler_quote_update(message):
#     print(f"quote update {message}")

# alice.start_websocket(subscribe_callback=event_handler_quote_update)

# alice.subscribe(alice.get_instrument_by_symbol('NSE', 'ONGC-EQ'), LiveFeedType.TICK_DATA)
# sleep(10)