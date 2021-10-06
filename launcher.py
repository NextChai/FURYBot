from bot import FuryBot
import logging

import os
from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)-15s] %(message)s')

if __name__ == '__main__':
    bot = FuryBot()
    bot.run(os.environ.get('TOKEN'), reconnect=True)
    