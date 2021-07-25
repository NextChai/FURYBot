import os
import logging
from dotenv import load_dotenv

from bot import Bot

load_dotenv()

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    bot = Bot()
    bot.nsfwAPI = os.environ.get('NUDITY_TOKEN')
    bot.run(os.environ.get("BOT_TOKEN"), reconnect=True)
    
