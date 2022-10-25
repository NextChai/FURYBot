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

import dotenv

dotenv.load_dotenv()  # pyright: ignore # This is out of my control


import asyncio
import logging
import os
from typing import TYPE_CHECKING

import aiohttp
import discord

from bot import FuryBot

if TYPE_CHECKING:
    import asyncpg

_log = logging.getLogger(__name__)

os.environ['JISHAKU_NO_UNDERSCORE'] = 'true'
os.environ['JISHAKU_NO_DM_TRACEBACK'] = 'true'
os.environ['JISHAKU_RETAIN'] = 'true'


async def main() -> None:
    discord.utils.setup_logging()

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    try:
        pool: asyncpg.Pool[asyncpg.Record] = await FuryBot.setup_pool(uri=os.environ['POSTGRES_URI'])
    except Exception as exc:
        return _log.warning('Failed to create the postgres pool.', exc_info=exc)

    session = aiohttp.ClientSession()

    try:
        bot = FuryBot(loop=loop, session=session, pool=pool)
    except Exception as exc:
        return _log.warning('Failed to create an instance of FuryBot.', exc_info=exc)

    async with bot, pool, session:
        await bot.start(os.environ['TOKEN'])


asyncio.run(main())
