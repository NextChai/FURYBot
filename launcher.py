import logging
from dotenv import dotenv_values

from bot import Bot

temp = dotenv_values(".env")

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    bot = Bot()
    bot.run(temp["BOT_TOKEN"], reconnect=True)
