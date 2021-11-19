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

import json
import asyncpg
import asyncio
import contextlib

import logging
from logging.handlers import RotatingFileHandler

from bot import FuryBot
from config import TOKEN, postgresql as uri


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
        # __enter__
        max_bytes = 32 * 1024 * 1024 # 32 MiB
        logging.getLogger('discord').setLevel(logging.INFO)
        logging.getLogger('discord.http').setLevel(logging.WARNING)
        logging.getLogger('discord.state').addFilter(RemoveNoise())

        log = logging.getLogger()
        log.setLevel(logging.INFO)
        handler = RotatingFileHandler(filename='scott.log', encoding='utf-8', mode='w', maxBytes=max_bytes, backupCount=5)
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(fmt)
        log.addHandler(handler)
        yield
    finally:
        # __exit__
        handlers = log.handlers[:] # type: ignore
        for hdlr in handlers:
            hdlr.close()
            log.removeHandler(hdlr) # type: ignore

async def setup_pool() -> asyncpg.Pool:
    def _encode_jsonb(value):
        return json.dumps(value)

    def _decode_jsonb(value):
        return json.loads(value)
    
    
    async def init(con):
        await con.set_type_codec('jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb, format='text')
            
    pool = await asyncpg.create_pool(uri, init=init)
    return pool
    
    
def run_bot():
    loop = asyncio.get_event_loop()
    log = logging.getLogger()
    
    try:
        pool = loop.run_until_complete(setup_pool())
    except Exception:
        log.exception('Could not setup PostgreSQL Pool, Exiting.')
        return
    
    fury = FuryBot()
    fury.pool = pool
    fury.run(TOKEN)
    
if __name__ == '__main__':
    with setup_logging():
        run_bot()