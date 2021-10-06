from bot import FuryBot
import logging

from config import TOKEN

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)-15s] %(message)s')

if __name__ == '__main__':
    bot = FuryBot()
    bot.run(TOKEN, reconnect=True)
    