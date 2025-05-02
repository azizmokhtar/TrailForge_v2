import os
import ast
from typing import Dict, Any

class ConfigManager:
    def __init__(self):
        self.config = {
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
            "WALLET_ADDRESS": os.getenv("WALLET_ADDRESS"),
            "PRIVATE_KEY": os.getenv("PRIVATE_KEY"),
            "TP": float(os.getenv("TP", "1")),
            "TTP_PERCENT": float(os.getenv("TTP_PERCENT", "0.05")),
            "BUY_SIZE": float(os.getenv("BUY_SIZE", "11")),
            "LEVERAGE": int(os.getenv("LEVERAGE", "5")),
            "MULTIPLIER": float(os.getenv("MULTIPLIER", "2")),
            "DEVIATIONS": [int(value) for value in ast.literal_eval(os.getenv("DEVIATIONS", "[1,1.6,6,13,29]"))],
            "RETRY_DELAY": int(os.getenv("RETRY_DELAY", "60")),
            "MAX_RETRIES": int(os.getenv("MAX_RETRIES", "50")),
            "HEARTBEAT_INTERVAL": int(os.getenv("HEARTBEAT_INTERVAL", "30")),
            "INITIAL_SYMBOLS": os.getenv("INITIAL_SYMBOLS", "HYPE,SUI,ADA").split(","),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "DEBUG_MODE": os.getenv("DEBUG_MODE", "False").lower() == "true",
        }

    def get(self, key: str, default=None) -> Any:
        return self.config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.config[key]