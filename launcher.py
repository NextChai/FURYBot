"""
The MIT License (MIT)

Copyright (c) 2020-present NextChai

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
from __future__ import annotations

import os
import traceback
import aiohttp
import asyncio
import logging
import contextlib
from typing import (
    Tuple,
)

from bot import FuryBot
from config import TOKEN

os.environ['JISHAKU_NO_UNDERSCORE'] = 'true'
os.environ['JISHAKU_NO_DM_TRACEBACK'] = 'true'
os.environ['JISHAKU_RETAIN'] = 'true'

logging.basicConfig(level=logging.INFO)

__all__: Tuple[str, ...] = ('RemoveNoise', 'setup_logging', 'run_bot')


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name='discord.state')

    def filter(self, record):
        if record.levelname == 'WARNING' and 'referencing an unknown' in record.msg:
            return False
        return True


@contextlib.contextmanager
def setup_logging():
    try:
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.state').addFilter(RemoveNoise())

        log = logging.getLogger('chai')
        log.setLevel(logging.INFO)

        ch = logging.StreamHandler()

        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
        ch.setFormatter(fmt)
        yield log
    finally:
        return


async def run_bot():
    try:
        pool = await FuryBot.setup_pool()
    except Exception:
        logging.warning('Could not setup PostgreSQL Pool, Exiting.')
        traceback.print_exc()
        raise

    loop = asyncio.get_event_loop()
    with setup_logging() as logger:
        async with pool:
            try:
                async with aiohttp.ClientSession() as session:
                    fury = FuryBot(pool=pool, session=session, loop=loop)
                    async with fury:
                        await fury.start(TOKEN, reconnect=True)
            except Exception as e:
                logger.warning('An unknown exception has occurred', exc_info=e)
            


if __name__ == '__main__':
    asyncio.run(run_bot())
