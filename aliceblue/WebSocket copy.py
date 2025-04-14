from pya3 import *

userId = "928693" 
apiKey = "RgYv3r8quYJD9uJXBD0mE8vxRvPaU3VDLzVb2gsvEDC7SILevtODCrUIusC74OMI4bpp0HhLz18VU8nbkJfbXutLVZFQt7DU1npKPds7L098ynWc6auHnZfDZuRIgdqM" 
alice = Aliceblue(user_id=userId,api_key=apiKey)

alice.get_session_id()

print(alice.get_balance()) # get balance / margin limits
print(alice.get_profile()) # get profile
print(alice.get_daywise_positions()) # get daywise positions
print(alice.get_netwise_positions()) # get all netwise positions
print(alice.get_holding_positions()) # get holding positions
 
alice.get_contract_master("NSE")

print(alice.get_instrument_by_symbol('NSE','INFY'))