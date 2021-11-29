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

import logging

from bot import FuryBot
from config import TOKEN, postgresql as uri, logging_webhook, message_webhook
logging.basicConfig(level=logging.INFO)

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
    fury.logging_webhook_url = logging_webhook
    fury.message_webhook_url = message_webhook
    fury.run(TOKEN)
    
if __name__ == '__main__':
    run_bot()