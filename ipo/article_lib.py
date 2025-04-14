from selenium import webdriver
from selenium.webdriver.common.by import By 
import time
import re 
import datetime
import requests

import mysql.connector
import pandas as pd

# Common function to connect to the database

def connect_to_db():
    db_config = {
        "host": "193.203.184.189",    
        "user": "u517303175_iVO6l",  
        "password": "U2DbPzwCPk", 
        "database": "u517303175_EsBGw"  
    }
    
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# Function to execute the SELECT query
def select_from_db( category = 'IPO', limit = 5 ):
    try:
        select_query = f"""
        SELECT
            DISTINCT wp_posts.post_title, wp_posts.guid, wp_term_taxonomy.taxonomy, wp_terms.name 
        FROM wp_posts
        LEFT JOIN wp_term_relationships ON (wp_posts.ID = wp_term_relationships.object_id)
        LEFT JOIN wp_term_taxonomy ON (wp_term_relationships.term_taxonomy_id = wp_term_taxonomy.term_taxonomy_id)
        LEFT JOIN wp_terms ON (wp_term_taxonomy.term_taxonomy_id = wp_terms.term_id)
        WHERE 
            wp_posts.post_status IN ('publish') 
            AND wp_posts.post_type IN ('post') 
            AND wp_term_taxonomy.taxonomy = 'category' 
            AND wp_terms.name = "{category}"
            AND wp_posts.ID not in (6405)
        ORDER BY wp_posts.post_modified_gmt DESC
        LIMIT {limit};
        """
        
        conn = connect_to_db()
        if conn is None:
            return None
        cursor = conn.cursor()
        cursor.execute(select_query)
        result = cursor.fetchall()
          
        df = pd.DataFrame(result, columns=['post_title', 'guid', 'taxonomy', 'name'])

        print( df )
        return df
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        # Close the database connection
        if conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")

# Read More section
def read_more_section(category = 'IPO', limit = 5):
    
    html_code = f"""
<!-- wp:paragraph -->
<p><strong>Read More :</strong></p>
<!-- /wp:paragraph -->
<!-- wp:paragraph -->
<p><a href="https://fundsandsavings.com/?p=6405">Live IPO Grey Market Price (GMP) Today</a> </p>
<!-- /wp:paragraph -->"""
    
    df = select_from_db(category = 'IPO', limit = 5)

    for i in range(len(df)):
        title = df.iloc[i][0]
        url = df.iloc[i][1]
    
        html_code +=  f"""
<!-- wp:paragraph -->
<p><a href="{url}">{title}</a> </p>
<!-- /wp:paragraph -->"""
    
    return html_code
