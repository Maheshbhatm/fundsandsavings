import sqlite3
import os
import pandas as pd
import json
import time as pytime
import logging

TICK_DATA_FILE = "/Users/mahesh/Documents/DE_learning/fundsandsavings/algo_trading/files/tick_stock_data_2025-04-07.txt"

DB_FILE = "ticks_data.db"

# Connect to SQLite (file-based)
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# Create ticks table (if not exists)
cursor.execute("""
CREATE TABLE IF NOT EXISTS ticks (
    token TEXT,
    high REAL,
    low REAL,
    open REAL,                
    close REAL,
    created_at TEXT,
    ft TEXT 
)
""")
conn.commit()

def delete_data():
    cursor.execute("DELETE FROM ticks")
    conn.commit()
    print("All rows deleted from ticks table.")

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

        # Handle missing fields
        for col in ["h", "l", "ap"]:
            df[col] = df[col].fillna(df["lp"]) if col in df.columns else df["lp"] 

        df["tk"] = df["tk"].astype(str)
        df["created_at"] = pd.to_datetime(df["ft"].apply(lambda x: pytime.strftime('%Y-%m-%d %H:%M:%S', pytime.localtime(int(x)))), errors='coerce')
        df["open"] = df["lp"] 

        # Rename columns to match DB
        df.rename(columns={
            "tk": "token",
            "h": "high",
            "l": "low",
            "open": "open",
            "lp": "close" 
        }, inplace=True)

        # Keep only needed columns
        df = df[["token", "high", "low", "open", "close", "created_at", "ft" ]] 

        print( df )
        return df

    except Exception as e:
        logging.error(f"❌ Error processing tick data: {e}")
        return None

def write_to_sqlite(df, db_file="ticks_data.db"):
    try:
        conn = sqlite3.connect(db_file)
        df.to_sql("ticks", conn, if_exists="append", index=False)
        conn.close()
        logging.info("✅ Tick data inserted into SQLite.")
    except Exception as e:
        logging.error(f"❌ Error writing to SQLite: {e}")

 
df = process_tick_data(TICK_DATA_FILE)
if df is not None:
    # delete_data()
    # write_to_sqlite(df)
    pass

cursor.execute("SELECT * FROM ticks ORDER BY created_at DESC LIMIT 10") 
rows = cursor.fetchall()
for row in rows :
    print(row)
