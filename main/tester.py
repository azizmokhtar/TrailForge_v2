import os
import ast
from dotenv import load_dotenv

load_dotenv()

retry_delay = int(os.getenv("CONNECTION_ERROR_RETRY_DELAY"))
max_retries = int(os.getenv("CONNECTION_ERROR_MAX_RETRIES"))
TP = float(os.getenv("TP"))
ttp_percent = float(os.getenv("TTP_PERCENT"))
leverage = int(os.getenv("LEVERAGE"))
buy_size = int(os.getenv("BUY_SIZE"))
multiplier = float(os.getenv("MULTIPLIER"))
deviations = ast.literal_eval(os.getenv("DEVIATIONS"))
user_address = os.getenv("PUBLIC_USER_ADDRESS")
initial_symbols = ast.literal_eval(os.getenv("INITIAL_SYMBOLS"))
TELEGRAM_LISTENER_BOT_TOKEN = os.getenv("TELEGRAM_LISTENER_TOKEN")

print(f"retry_delay: {retry_delay} ({type(retry_delay)})")
print(f"max_retries: {max_retries} ({type(max_retries)})")
print(f"TP: {TP} ({type(TP)})")
print(f"ttp_percent: {ttp_percent} ({type(ttp_percent)})")
print(f"leverage: {leverage} ({type(leverage)})")
print(f"buy_size: {buy_size} ({type(buy_size)})")
print(f"multiplier: {multiplier} ({type(multiplier)})")
print(f"deviations: {deviations} ({type(deviations)})")
print(f"user_address: {user_address} ({type(user_address)})")
print(f"initial_symbols: {initial_symbols} ({type(initial_symbols)})")
print(f"TELEGRAM_LISTENER_BOT_TOKEN: {TELEGRAM_LISTENER_BOT_TOKEN} ({type(TELEGRAM_LISTENER_BOT_TOKEN)})")
