import os
import logging
from dotenv import load_dotenv

from bot import FuryBot

load_dotenv()

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    bot = FuryBot()
    
    bot.nsfwAPI = os.environ.get('NUDITY_TOKEN')
    bot.trnAPIHeaders = {'TRN-Api-Key': os.environ.get('TRN-Api-Key')}
    
    bot.run(os.environ.get("BOT_TOKEN"), reconnect=True)
    