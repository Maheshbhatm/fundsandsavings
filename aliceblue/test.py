def collect_market_data():
    logging.info("🔄 Starting Market Data Collection (9:15 AM - 9:20 AM)...")
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
    logging.info(f"✅ Subscribed to {len(stock_tokens)} Stock Tokens")
    
    if not os.path.exists(TICK_DATA_FILE):
        with open(TICK_DATA_FILE, 'w') as file:
            pass   

    top_loser_check = False
    
    while True: 
        all_tick_data_df = process_tick_data()
        
        if not top_loser_check and datetime.now() > end_time:
            top_loser_check = True
            top_losers_df = get_top_losers()
            top_losers_df["trade_executed"] = "NO"
            top_losers_df["target_executed"] = "NO"
        
        elif top_loser_check:
            try:
                for index, loser in top_losers_df.iterrows():
                    stock_token = loser['Token'] 
                    low_price = loser['low']
                    latest_data = all_tick_data_df[all_tick_data_df['tk'] == str(stock_token)]
                    
                    if not latest_data.empty:
                        latest_price = latest_data['lp'].dropna().iloc[-1] 
                        
                        if loser['trade_executed'] == "NO" and latest_price <= low_price:
                            logging.info(f"📉 Low broken for {stock_token} at {latest_price}, executing trade...")
                            
                            stock_latest_data = get_all_data_fno()
                            stock_latest_data = stock_latest_data[stock_latest_data['tk'] == stock_token]
                            
                            if not stock_latest_data.empty:
                            
                                quantity = int(loser['Lot Size']) * (BUDGET // (int(loser['Lot Size']) * (latest_price / 5)))
                                tick_size = float(loser['Tick Size'])
                                
                                order_response = place_order('SELL', 'NSE', stock_token, stock_token, loser['Trading Symbol'], quantity, latest_price)
                                data = json.loads(order_response)
                                
                                if isinstance(data, list) and data and "stat" in data[0] and data[0]["stat"] == "Ok":
                                    top_losers_df.at[index, "trade_executed"] = "YES"
                                    logging.info(f"✅ Order placed successfully! Order ID: {data[0].get('NOrdNo', 'Unknown')}")
                                else:
                                    logging.error("❌ Order placement failed or invalid response.")

                        elif loser['trade_executed'] == "YES" and loser['target_executed'] == "NO":
                            super_trend = check_super_trend(stock_token)
                            if super_trend == -1:
                                logging.info(f"📊 Super trend reversed for {stock_token}, placing order...")
                                
                                order_response = place_order('BUY', 'NSE', stock_token, stock_token, loser['Trading Symbol'], quantity, latest_price)
                                top_losers_df.at[index, "target_executed"] = "YES"
                                logging.info(f"✅ Buy order placed at {latest_price}")

                if datetime.now().hour == 15:
                    pending_orders = top_losers_df[top_losers_df['target_executed'] == "NO"]
                    for _, row in pending_orders.iterrows():
                        place_order('BUY', 'NSE', row['Token'], row['Token'], row['Trading Symbol'], quantity, latest_price)
                        logging.info(f"✅ Final order placed for {row['Token']} at {latest_price}")
                    break  
            except Exception as e:
                logging.error(f"❌ Error: {e}")
