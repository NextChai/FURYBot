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

from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from utils.bases.cog import BaseCog
from utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot

class Owner(BaseCog):

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.group(name='profanity', description='Manage the profanity filter.', invoke_without_command=True)
    async def profanity(self, ctx: Context) -> Optional[discord.Message]:
        if ctx.invoked_subcommand:
            return
        
        return await ctx.send('No subcommand sent.')
    
    @profanity.command(name='remove', description='Remove a profane word.')
    async def profanity_remove(self, ctx: Context, *, word: str) -> discord.Message:
        async with self.bot.safe_connection() as connection:
            data = await connection.execute('DELETE FROM profane_words WHERE word = $1', word)
        
        return await ctx.send(data)

    @profanity.command(name='add', description='Add a profane word.')
    async def profanity_add(self, ctx: Context, *, word: str) -> discord.Message:
        async with self.bot.safe_connection() as connection:
            data = await connection.execute("INSERT INTO profane_words(word) VALUES ($1) ON CONFLICT (word) DO NOTHING", word)
        
        return await ctx.send(data)

async def setup(bot: FuryBot):
    await bot.add_cog(Owner(bot))