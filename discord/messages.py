# import sys
# sys.path.append('../')
import requests 
from dotenv import load_dotenv
import os
import discord
import logging

output_msgs_flag = True

# Load environment variables from .env file
load_dotenv()

# Access variables from the .env file
discord_key = os.getenv('discord_key')

# Configure logging for discord_msgs
logger = logging.getLogger(__name__)

def send_msg(msg, strat='orb', toPrint=False):
    # print(f'sending message: {msg}')

    bot_url = None
    if strat == 'bitcoin-trader':
        bot_url = "https://discord.com/api/webhooks/1452228163580198943/RPYtHFA79iJ31qKotlDkhNmzkuJcEyLDVoDshsTQMF5qPqh7flHbXbsOIk2Xm1-4Km20"
    else:
        logger.warning(f'Unknown strategy "{strat}" for Discord message: {msg}')
        return

    if bot_url is None:
        logger.error(f'No Discord webhook URL configured for strategy "{strat}"')
        return

    payload = {
        "content": f"{msg}",
    }

    headers = {
        "Authorization" : discord_key
    }
    try: 
        res = requests.post(bot_url, json=payload, headers=headers)
        if res.status_code not in [200, 204]:
            logger.error(f'Discord API error: {res.status_code} - {res.text}')
        else:
            logger.debug(f'Discord message sent successfully: {msg}')
    except Exception as e:
        logger.error(f'Error sending Discord message: {e}')

    if toPrint:
        print(f'{msg}')

def speak_msg(msg):

    # Initialize the TTS engine
    # engine = pyttsx3.init()

    # # Set properties (optional)
    # engine.setProperty('rate', 150)  # Speed of speech
    # engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0)

    # Speak the text
    # engine.say(msg)
    # engine.runAndWait()

    #send_sms.send_whatsapp_msg(msg)
    #subprocess.run(['say', msg])  # for windows
    os.system(f'say "{msg}"') # for macos


def output_msg(msg, speak = False, strat='orb'):
    
    if output_msgs_flag:
        #send_sms.send_whatsapp_msg(msg)
        send_msg(msg, strat) # send msgs with discord

        #print(msg)

        if speak:
            speak_msg(msg)


def send_strategy_status_update(status: str, live_mode: bool):
    """
    Sends a Discord notification about the strategy's status (started/stopped).

    Args:
        status (str): The status of the strategy, either "started" or "stopped".
        live_mode (bool): A flag indicating if the strategy is in live mode.
    """
    mode_text = "Live" if live_mode else "Paper"
    
    if status == "started":
        message = f"✅ Straddle Strategy Started ({mode_text} Mode)."
    elif status == "stopped":
        message = f"🛑 Straddle Strategy Stopped ({mode_text} Mode)."
    else:
        logger.warning(f"Unknown status '{status}' for strategy status update.")
        return

    channel = 'live-stop-hunter' if live_mode else 'paper-stop-hunter'
    
    send_msg(message, strat=channel)

async def notify_partial_fill(
    position_id: str,
    symbol: str,
    strategy_name: str,
    filled_quantity: int,
    total_quantity: int,
    fill_price: float,
    remaining_quantity: int
) -> None:
    """
    Send Discord notification when a partial fill occurs.
    """
    message = (
        f"⚠️ **PARTIAL FILL** - {strategy_name}\n"
        f"Symbol: {symbol}\n"
        f"Filled: {filled_quantity}/{total_quantity} contracts @ ${fill_price:.2f}\n"
        f"Remaining: {remaining_quantity} contracts\n"
        f"Position ID: `{position_id}`"
    )
    
    # send_msg is synchronous, but we can wrap it or just call it 
    # (requests.post blocks, but likely fast enough for this alert)
    send_msg(message, strat='auto-trader-pro')
    logger.info(f"Sent partial fill notification for {position_id}")

if __name__ == '__main__':
    send_msg("test", strat='spread_test')
