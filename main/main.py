import os
import ast
import json
import logging
import asyncio
import websockets
from logging.handlers import RotatingFileHandler
from managers.PositionCatalogue import PositionCatalogue
from managers.SymbolManager import SymbolManager
from telegram_endpoint.TelegramMessenger import Messenger
from telegram_endpoint.BotListener import TelegramBotListener
from executors.HyperliquidUtils import HyperliquidUtils
from dotenv import load_dotenv
from config.configManager import ConfigManager

load_dotenv()
config = ConfigManager()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs to console
        RotatingFileHandler(
            'bot.log',
            maxBytes=5 * 1024 * 1024,  # 10 MB
            backupCount=3  # Keep up to 5 backup files
        )
    ]
)
logger = logging.getLogger(__name__)

def format_symbol(symbol: str) -> str:
    return f"{symbol}/USDC:USDC"

async def subscribe_user_fills(user_address: str,
                               buy_size: float,
                               position_manager: PositionCatalogue,
                               hyperliquid_executor: HyperliquidUtils,
                               symbol_manager: SymbolManager,
                               TP: float,
                               deviations: list,
                               multiplier: float,
                               leverage: int,
                               ttp_percent: float,
                               telegram: Messenger,
                               retry_delay: int,
                               max_retries:int):
    uri = "wss://api.hyperliquid.xyz/ws"

    # Connection error retrial settings
    retry_delay = retry_delay 
    max_retries = max_retries  
    retry_count = 0  

    #Running loop
    while True:  
        try:
            logger.info("Attempting to connect to WebSocket...")
            async with websockets.connect(uri) as websocket:
                # Reset retry count on successful connection
                retry_count = 0
                logger.info(f"Connected to WebSocket. Subscribing to user fills for address: {user_address}")
                # Construct the subscription message for user fills
                subscribe_message = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "webData2",
                        "user": user_address
                    }
                }
                await websocket.send(json.dumps(subscribe_message))
                logger.info(f"Subscribed to user fills for address: {user_address}")
                # Heartbeat Ping Pong mechanism to not prevent websicket connection from going idle
                async def send_heartbeat():
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await websocket.send(json.dumps({"method": "ping"}))
                            logger.debug("→ Sent ping")
                        except websockets.exceptions.ConnectionClosed:
                            logger.error("Connection closed while sending heartbeat")
                            break
                # Core Event based decision making mechanism as soon as receiving position info
                async def receive_messages():                   
                    while True:
                        try:
                            # Receive the websocket message and validate and format the needed info
                            message = await websocket.recv()
                            try:
                                data = json.loads(message)
                            except json.JSONDecodeError as e:
                                logger.error(f"Error decoding JSON from WebSocket message: {e}")
                                await telegram.send_message(text=f'- ERROR - error with json ws data')
                                continue
                            if data.get("channel") == "webData2":
                                clearinghouse_state = data.get("data", {}).get("clearinghouseState", {})
                                asset_positions = clearinghouse_state.get("assetPositions", [])
                                if asset_positions:
                                    # Iterate over every position open detected by the Hyperliquid infrasutructure
                                    for pos in asset_positions:
                                        # Fetch needed data for calculations
                                        position_data = pos.get("position", {})
                                        coin = position_data.get("coin", "UNKNOWN")
                                        #print(f"Iterating through {coin}:")
                                        szi = float(position_data.get("szi", 0))
                                        entry_px = float(position_data.get("entryPx", 0))
                                        position_value = float(position_data.get("positionValue", 0))
                                        unrealized_pnl = float(position_data.get("unrealizedPnl", 0))
                                        roe = float(position_data.get("returnOnEquity", 0))
                                        pnl_percent = ((unrealized_pnl / position_value)*100 ) #* leverage
                                        position = position_manager.get_position(coin)
                                        # If we have a position open, but it's not recorded
                                        if position is None:
                                            position_manager.add_position(
                                                symbol=coin, average_buy_price=entry_px, pnl=pnl_percent,
                                                size_in_dollars=position_value, size_in_quote=szi, limit_orders={}, ttp_active=False
                                            )
                                            await telegram.send_message(text=f'ERROR: open {coin} position found, where we do not know its source! Saved in db but will be a problem by closing.')
                                            continue
                                        # If we are over pnl goal, activate trailing take profit 
                                        elif pnl_percent >= TP and position["ttp_active"] == False:
                                            print(f"pnl percent hit for {coin}, activating trailing")
                                            position_manager.update_position(
                                                symbol=coin, average_buy_price=entry_px, pnl=pnl_percent,
                                                size_in_dollars=position_value, size_in_quote=szi, ttp_active=True
                                            )
                                            logger.info(f"ttp activated for {coin}")
                                            continue
                                        # If trailing is active and we hit TTP limit
                                        elif position["ttp_active"]:
                                            if position.get("peak_pnl", 0) - pnl_percent >= ttp_percent:
                                                try:
                                                    logger.info(f"Exiting {coin} position in profit")
                                                    ticker = format_symbol(coin)
                                                    await hyperliquid_executor.leveraged_market_close_Order(ticker, "buy")
                                                    position = position_manager.get_position(coin)
                                                    limit_orders = position["limit_orders"]
                                                    await hyperliquid_executor.cancelLimitOrders(deviations, ticker, limit_orders)
                                                    logger.info(f"Closed {coin} position with {pnl_percent}%")
                                                    await telegram.send_message(text=f'Closed {coin} position with {pnl_percent}%')
                                                    # Check if we sent a removal of symbol order through Telegram
                                                    remove_decision = await symbol_manager.is_pending_removal(coin)
                                                    if remove_decision == False:
                                                        logger.info(f"{coin} still useful, opening new position.")
                                                        await asyncio.sleep(1)
                                                        order = await hyperliquid_executor.leveragedMarketOrder(ticker, "buy", buy_size)
                                                        limit_orders = await hyperliquid_executor.create_batch_limit_buy_order_custom_dca(
                                                            order[0], buy_size, multiplier, ticker, deviations
                                                        )
                                                        await telegram.send_message(text=f'Opening {coin} first position.')
                                                        position_manager.update_position(
                                                            symbol=coin, average_buy_price=order[0], pnl=0.0,
                                                            size_in_dollars=11, size_in_quote=69, limit_orders=limit_orders, ttp_active=False
                                                        )
                                                        await asyncio.sleep(1)
                                                        logger.info(f"finished opening new {coin} position.")
                                                    # If no removal decision detected
                                                    else:
                                                        await telegram.send_message(text=f'exited {coin} position safely, no more buying.')
                                                        logger.info(f"exited {coin} position safely, no more buying.")
                                                        position_manager.delete_position(coin)
                                                except Exception as e:
                                                    logger.error(f"Error with closing/opening new order for {coin}: {e}")
                                                    await telegram.send_message(text=f'ERROR - Error with closing/opening new order:{e}')
                                        # If still not in profit or ttp active
                                        elif position_manager.has_position(coin):
                                            position_manager.update_position(
                                                symbol=coin, average_buy_price=entry_px, pnl=pnl_percent,
                                                size_in_dollars=position_value, size_in_quote=szi
                                            )

                                    #print("Finished checking on old/existing tickers, time to see if we have new...")
                                    # Check the telegram symbol manager: if we have a new ordered position(Position not in position manager), open it and save it in position_manager 
                                    current_active_symbols = await symbol_manager.get_active_symbols()
                                    ##print(current_active_symbols)
                                    for symbol in current_active_symbols:
                                        try:
                                            if not position_manager.has_position(symbol):
                                                #logger.info(f"New symbol added: {symbol}, opening position...")
                                                try:
                                                    logger.info(f"New symbol added on telegram: {symbol}, opening position... ")
                                                    ticker = format_symbol(symbol)
                                                    await hyperliquid_executor.setLeverage(leverage, ticker)
                                                    order = await hyperliquid_executor.leveragedMarketOrder(ticker, "buy", buy_size)
                                                    limit_orders = await hyperliquid_executor.create_batch_limit_buy_order_custom_dca(
                                                        order[0], buy_size, multiplier, ticker, deviations
                                                    )
                                                    position_manager.add_position(
                                                        symbol=symbol, average_buy_price=order[0], pnl=0.0,
                                                        size_in_dollars=buy_size, size_in_quote=0, limit_orders=limit_orders, ttp_active=False
                                                    )
                                                    await telegram.send_message(text=f'Opened new position for: {symbol}')
                                                    logger.info(f"{symbol} position opened successfully! ")
                                                except Exception as e:
                                                    logger.error(f"Error opening first position for {symbol}: {e}")
                                                    await telegram.send_message(text=f'- ERROR - Failed to open position for {symbol}: {e}')
                                        except Exception as e:
                                            logger.error(f"Error opening position for {symbol}: {e}")
                                            await telegram.send_message(text=f'- ERROR - Failed to open position for {symbol}: {e}')

                        except websockets.exceptions.ConnectionClosed:
                            logger.error("WebSocket connection closed unexpectedly")
                            await telegram.send_message(text=f'- ERROR - error with ws data')
                            break

                # Run heartbeat and message handling concurrently
                await asyncio.gather(
                    send_heartbeat(),
                    receive_messages()
                )

        except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
            logger.error(f"WebSocket connection lost: {e}. Retrying in {retry_delay} seconds...")
            await telegram.send_message(text=f'- ERROR - WebSocket connection lost: {e}. Retrying in {retry_delay} seconds...')
            retry_count += 1  # Increment retry counter
            if retry_count > max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded. Giving up.")
                await telegram.send_message(text=f'- ERROR - Max retries ({max_retries}) exceeded. Giving up.')
                break
            await asyncio.sleep(retry_delay)

        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in {retry_delay} seconds...")
            await telegram.send_message(text=f'- ERROR - Unexpected error: {e}. Retrying in {retry_delay} seconds...')
            retry_count += 1  # Increment retry counter
            if retry_count > max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded. Giving up.")
                await telegram.send_message(text=f'- ERROR - Max retries ({max_retries}) exceeded. Giving up.')
                break
            await asyncio.sleep(retry_delay)

async def main():

    # Program variables, change in .env file
    logger.info("Assignining variables...")
    retry_delay = int(os.getenv("CONNECTION_ERROR_RETRY_DELAY"))
    max_retries = int(os.getenv("CONNECTION_ERROR_MAX_RETRIES"))
    TP = float(os.getenv("TP"))
    ttp_percent = float(os.getenv("TTP_PERCENT"))
    leverage = int(os.getenv("LEVERAGE"))
    buy_size = int(os.getenv("BUY_SIZE"))
    multiplier = float(os.getenv("MULTIPLIER"))
    deviations = ast.literal_eval(os.getenv("DEVIATIONS"))
    deviations = [int(value) for value in deviations]
    user_address = os.getenv("PUBLIC_USER_ADDRESS")
    initial_symbols = ast.literal_eval(os.getenv("INITIAL_SYMBOLS"))
    TELEGRAM_LISTENER_BOT_TOKEN = os.getenv("TELEGRAM_LISTENER_TOKEN")
    TELEGRAM_MESSENGER_BOT_TOKEN = os.getenv("TELEGRAM_MESSENGER_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("MESSENGER_CHAT_ID")
    
    
    # Helping instances init
    logger.info("Initializing...")
    telegram = Messenger(TELEGRAM_MESSENGER_BOT_TOKEN, TELEGRAM_CHAT_ID)
    position_manager = PositionCatalogue()
    position_manager.clear_all_positions()
    symbol_manager = SymbolManager(initial_symbols)
    hyperliquid_executor = await HyperliquidUtils.create()
    bot_listener = TelegramBotListener(TELEGRAM_LISTENER_BOT_TOKEN, symbol_manager)
    
    await telegram.send_message(text=f'Starting bot ')

    # Open initial positions for symbols
    logger.info("Initial round of buys launching...")
    for symbol in await symbol_manager.get_active_symbols():
        ticker = format_symbol(symbol)
        try:
            await hyperliquid_executor.setLeverage(leverage, ticker)
            logger.info(f"Set leverage for {symbol}")
            order = await hyperliquid_executor.leveragedMarketOrder(ticker, "buy", buy_size)
            limit_orders = await hyperliquid_executor.create_batch_limit_buy_order_custom_dca(
                order[0], buy_size, multiplier, ticker, deviations
            )
            position_manager.add_position(
                symbol=symbol, average_buy_price=order[0], pnl=0.0,
                size_in_dollars=buy_size, size_in_quote=0,
                limit_orders=limit_orders, ttp_active=False
            )
            logger.info(f"Opened first position for {symbol}")
            await telegram.send_message(text=f'Opened first position for: {symbol}')
        except Exception as e:
            logger.error(f"Error placing first order for {symbol}: {e}")
            await telegram.send_message(text=f'ERROR - Error placing first order for: {symbol}')

    logger.info("Firing telegram listener in background...")
    # Starrt telegram listener on background
    asyncio.create_task(bot_listener.start())  
    logger.info("Running main loop...")
    await asyncio.sleep(5) 
    await subscribe_user_fills( # Start WebSocket processing
        user_address=user_address,
        buy_size=buy_size,
        position_manager=position_manager,
        hyperliquid_executor=hyperliquid_executor,
        symbol_manager=symbol_manager,
        TP=TP,
        deviations=deviations,
        multiplier=multiplier,
        leverage=leverage,
        ttp_percent=ttp_percent,
        telegram=telegram,
        retry_delay = retry_delay,
        max_retries = max_retries
    )


if __name__ == "__main__":
    asyncio.run(main())