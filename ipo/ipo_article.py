from  article_lib import *

from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import time
import re
import mysql.connector
from datetime import datetime

import random
import requests

file_path = './ipo/source_formate.html'

# Open and read the HTML file
with open(file_path, 'r', encoding='utf-8') as file:
    html_content = file.read() 


# Code

var_stock_name1 = 'Shri Ahimsa Naturals NSE SME'
var_price_range = '119'
var_gmp_amount = '0'
var_gmp_percentage = '0%'
var_issue_size = '73.81 Cr'
var_number_of_shares = '1200'
var_open_date = '2025-03-25'
var_close_date = '2025-03-27'
var_allotment_date = '2025-03-28'
var_list_date = '2025-04-02'
var_stock_name2 = 'Shri Ahimsa Naturals'
var_stock_name3 = 'Shri Ahimsa Naturals IPO'
var_max_lot = '1'
var_price_range = [113, 119] 

var_one_lot_value = var_price_range[1] * int( var_number_of_shares ) 
if var_price_range[0] == 0:
    var_price_range_txt = f"The price for the shares is ₹{var_price_range[1]}."
else:
    var_price_range_txt = f"The price range for the shares is ₹{var_price_range[0]} to ₹{var_price_range[1]}."

if var_price_range[0] == 0:
    var_price_range_table = f"₹{var_price_range[1]} Per Share"
else:
    var_price_range_table = f"₹{var_price_range[0]} to ₹{var_price_range[1]} Per Share"


var_allotment_date = datetime.strptime(var_allotment_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
var_list_date =  datetime.strptime(var_list_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
var_open_date = datetime.strptime(var_open_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
var_close_date = datetime.strptime(var_close_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
# var_open_date = datetime.strptime(var_open_date, "%Y-%m-%d").strftime("%d %B %Y")
# var_close_date = datetime.strptime(var_close_date, "%Y-%m-%d").strftime("%d %B %Y")
  
# Replace placeholders with variable values
html_content = html_content.replace("{var_stock_name1}", var_stock_name1 )
html_content = html_content.replace("{var_stock_name2}", var_stock_name2 )
html_content = html_content.replace("{var_stock_name3}", var_stock_name3 )
html_content = html_content.replace("{var_allotment_date}", var_allotment_date)
html_content = html_content.replace("{var_list_date}", var_list_date)
html_content = html_content.replace("{var_open_date}", var_open_date)
html_content = html_content.replace("{var_close_date}", var_close_date)
html_content = html_content.replace("{var_issue_size}", var_issue_size)
html_content = html_content.replace("{var_number_of_shares}", str(var_number_of_shares))
html_content = html_content.replace("{var_price_range_txt}", str(var_price_range_txt))
html_content = html_content.replace("{var_one_lot_value}", str(var_one_lot_value))
html_content = html_content.replace("{var_max_lot}", str(var_max_lot))
html_content = html_content.replace("{var_gmp_percentage}", var_gmp_percentage)
html_content = html_content.replace("{var_gmp_amount}", var_gmp_amount)
html_content = html_content.replace("{var_price_range_table}", var_price_range_table)

formatted_html = html_content 

formatted_html += read_more_section(category = 'IPO', limit = 5)

# print(formatted_html)

file_path = f'./ipo/files/{var_stock_name1}.html'
with open(file_path, "w") as file:
    file.write(formatted_html)