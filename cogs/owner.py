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

import io
import logging
import platform
import traceback
import contextlib
from typing import (
    TYPE_CHECKING,
)

import discord
from discord.ext import commands

from jishaku.modules import ExtensionConverter
from jishaku.repl.compilation import AsyncCodeExecutor
from jishaku.repl.scope import Scope
from jishaku.codeblocks import codeblock_converter

from utils import BaseCog, Context, tick
from utils.paginator import AsyncCodePaginator

if TYPE_CHECKING:
    from bot import FuryBot
    
log = logging.getLogger(__name__)

    
class Owner(BaseCog):
    
    async def cog_check(self, ctx: Context[FuryBot]) -> bool:
        return await self.bot.is_owner(ctx.author)
    
    @commands.command(name='load', description='Loads an extension.', aliases=['reload',])
    async def load(self, ctx: Context[FuryBot], *, extensions: ExtensionConverter) -> discord.Message:
        """|coro|
        
        Loads / reloads an extension.
        
        Parameters
        ----------
        extensions: :class:`str`
            The extension(s) to load / reload.
        """
        stauses = []
        for extension in extensions:
            if extension not in self.bot.extensions:
                try:
                    await self.bot.load_extension(extension)
                except Exception as exc:
                    log.warning('Could not load extension %s', extension, exc_info=exc)
                    stauses.append(tick(False, f'`{extension}`'))
                else:
                    stauses.append(tick(True, f'`{extension}`'))
            else:
                try:
                    await self.bot.reload_extension(extension)
                except Exception as exc:
                    log.warning('Could not reloadload extension %s', extension, exc_info=exc)
                    stauses.append(tick(False, f'`{extension}`'))
                else:
                    stauses.append(tick(True, f'`{extension}`'))
        
        return await ctx.send('\n'.join(stauses))
    
    @commands.command(name='unload', description='Unloads an extension.')
    async def unload(self, ctx: Context[FuryBot], *, extensions: ExtensionConverter) -> discord.Message:
        """|coro|
        
        Unloads an extension.
        
        Parameters
        ----------
        extensions: :class:`str`
            The extension(s) to unload.
        """
        stauses = []
        for extension in extensions:
            if extension in self.bot.extensions:
                try:
                    await self.bot.unload_extension(extension)
                except Exception as exc:
                    log.warning('Could not unload extension %s', extension, exc_info=exc)
                    stauses.append(tick(False, f'`{extension}`'))
                else:
                    stauses.append(tick(True, f'`{extension}`'))
            else:
                stauses.append(tick(False, f'`Not loaded: {extension}`'))
        
        return await ctx.send('\n'.join(stauses))
    
    @commands.command(name='python', description='Execute Python code and get the result.', aliases=['py'])
    async def python(self, ctx: Context[FuryBot], *, code: codeblock_converter) -> None:
        """|coro|
        
        Execute Python code and return the result.
        
        Parameters
        ----------
        code: :class:`str`
            The code to execute.
        """
        custom_globals = {
            'ctx': ctx,
            'context': ctx,
            'guild': ctx.guild,
            'message': ctx.message,
            'self': self,
            'bot': ctx.bot,
            'cog': self,
        }
        custom_globals.update(globals())
        
        await ctx.trigger_typing()
        
        version_info = f'+ Running Python {platform.python_version()} ({platform.system()}), W/ Compiler {platform.python_compiler()}'
        message = await ctx.send(f'```diff\n{version_info}```')
        
        paginator = AsyncCodePaginator(message, ctx.author, prefix='```diff')
        await paginator.add_line(version_info) # This ensures the python info is kept
        
        # Checks and redirect stdout info
        redirected = []
        contained_content: bool = False
        
        stringity = io.StringIO()
        scope = Scope(custom_globals, locals())
        with contextlib.redirect_stdout(stringity):
            try:
                async for line in AsyncCodeExecutor(code.content, scope=scope, loop=self.bot.loop):
                    if line:
                        contained_content = True
                        await paginator(str(line))
                    
                    decoded = stringity.getvalue()
                    if decoded != '' and (not redirected) or (redirected and redirected[-1] != decoded):
                        redirected.append(decoded)
                        contained_content = True
                        await paginator(decoded)
            except Exception as exc:
                traceback_string = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                await paginator(traceback_string)
                
        if not contained_content:
            await paginator('Code ran with no output.')
    
async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Owner(bot))