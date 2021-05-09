from bot import Bot
from dotenv import load_dotenv
import os
import logging
load_dotenv()


logging = logging.getLogger(__name__)

if __name__ == "__main__":
    bot = Bot()
    bot.run(os.environ.get("BOT_TOKEN"), reconnect=True)
