import logging
from dotenv import Dotenv

from bot import Bot

temp = Dotenv(".env")

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    bot = Bot()
    bot.run(temp["BOT_TOKEN"], reconnect=True)
