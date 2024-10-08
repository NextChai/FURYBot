"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to
non-commercial purposes. Distribution, sublicensing, and sharing of this file
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not
misrepresent the original material. This license does not grant any
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import aiohttp
import discord
import dotenv

from bot import FuryBot

if TYPE_CHECKING:
    import asyncpg

dotenv.load_dotenv()

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
        try:
            await bot.start(os.environ['TOKEN'])
        except Exception as exc:
            return _log.warning('Failed to start client.', exc_info=exc)


asyncio.run(main())
