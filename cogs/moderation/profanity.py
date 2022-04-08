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

from typing import (
    Optional,
)

import discord
from discord.ext import commands

from utils import BaseCog
from utils.context import Context


def to_lower(argument: str) -> str:
    return argument.lower()


class Profanity(BaseCog):
    
    @commands.command(
        name='censor',
        brief='Censor a word or phrase.',
        description='Use fury bot to censor a word or phrase.',
        aliases=['censorword', 'censortext', 'censortexts', 'censorphrase', 'censorphrases']
    )
    async def censor(self, ctx: Context, *, phrase: str) -> None:
        return await self.profanity_censor(ctx, sentence=phrase)
    
    @commands.group(
        name='profanity', 
        brief='Manage the profanity filter',
        description='Manage the profanity filter',
        aliases=['p', 'profanityfilter'],
        invoke_without_command=True
    )
    async def profanity(self, ctx: Context, *, sentence: str) -> None:
        if ctx.invoked_subcommand:
            return
        
        censored = await self.bot.censor(sentence)
        await ctx.send(f'`{censored}`')
        
    @profanity.command(
        name='add', 
        brief='Add a word to the profanity filter',
        description='Add a word to the profanity filter',
        aliases=['a', 'addword']
    )
    async def profanity_add(self, ctx: Context, *, word: str = commands.parameter(converter=to_lower)) -> Optional[discord.Message]:
        profanity = await self.bot.profanity.get_profane_words()
        if word in profanity:
            return await ctx.send(f'`{word}` is already in the profanity filter.')  
        
        async with self.bot.safe_connection() as connection:
            await connection.execute('INSERT INTO profanity (word) VALUES ($1)', word)

        self.bot.profanity._profanity.append(word) # type: ignore
        await ctx.send(f'`{word}` has been added to the profanity filter.')
        
    @profanity.command(
        name='remove',
        brief='Remove a word from the profanity filter',
        description='Remove a word from the profanity filter',
        aliases=['r', 'removeword']
    )
    async def profanity_remove(self, ctx: Context, *, word: str = commands.parameter(converter=to_lower)) -> Optional[discord.Message]:
        profanity = await self.bot.profanity.get_profane_words()
        if word not in profanity:
            return await ctx.send(f'`{word}` is not in the profanity filter.') 
        
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM profanity WHERE word = $1', word)

        self.bot.profanity._profanity.remove(word) # type: ignore
        await ctx.send(f'`{word}` has been removed from the profanity filter.')
    
    @profanity.command(
        name='censor',
        brief='Censor a sentence',
        description='Censor a sentence to see if it contains profanity',
        aliases=['c']
    )
    async def profanity_censor(self, ctx: Context, *, sentence: str) -> None:
        censored = await self.bot.censor(sentence)
        await ctx.send(f'{sentence} -> `{censored}`')
    