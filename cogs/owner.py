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

import re
import time
from typing import (
    TYPE_CHECKING,
)

import discord
from discord.ext import commands

from jishaku.shell import ShellReader

from utils import BaseCog
from utils.context import Context
from utils.paginator import AsyncCodePaginator

if TYPE_CHECKING:
    from bot import FuryBot

_GIT_PULL_REGEX: re.Pattern = re.compile(r'(?P<path>(?:[a-z]{1,}/){1,})(?P<filename>[a-z]{1,}).py')



class Owner(BaseCog):
    
    @commands.command(name='git')
    async def git(self, ctx: Context, *, argument: str = 'pull') -> None:
        """|coro|
        
        Used to perform a git operation and return the output. This is a
        special command, in which if `git pull` is called it will display
        a view to the user to reload any extensions.
        """
        message = await ctx.send('Starting...')
        paginator = AsyncCodePaginator(message=message, author=ctx.author, prefix='```py')
        start = None
        
        with ShellReader(f'git {argument}', loop=self.bot.loop) as reader:
            async for line in reader:
                if not start:
                    start = time.time()
                    update = True
                elif time.time() - start > 1:
                    start = time.time()
                    update = True
                else:
                    update = False
                
                await paginator.add_line(line, update_message=update)
        
        
async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Owner(bot))