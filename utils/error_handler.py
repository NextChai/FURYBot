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

import traceback
import logging
from typing import (
    TYPE_CHECKING,
    Optional,
)

import discord
from discord.ext import commands

from .context import Context
from .errors import *

if TYPE_CHECKING:
    import inspect
    
    from bot import FuryBot
    
log = logging.getLogger(__name__)
    
async def on_command_error(ctx: Context, error: commands.CommandError) -> Optional[discord.Message]:
    command = ctx.command
    if not command:
        return
    
    if isinstance(error, (commands.CommandNotFound, )): # Ignored errors
        return
    if isinstance(error, commands.MemberNotFound):
        return await ctx.send(f'The member "{error.argument}" was not found.')
    if isinstance(error, commands.CheckFailure):
        return await ctx.send('Ope! You can not run this command, you are not qualified to.')
    if isinstance(error, commands.TooManyArguments):
        total_args = len(command.clean_params)
        return await ctx.send(f'Ope! You passed too many parameters to this command. There should only be {total_args} parameters total.')
    if isinstance(error, commands.MissingRequiredArgument):
        required_param: inspect.Parameter = error.param
        return await ctx.send(f'Ope! You are missing the required parameter named `{required_param.name}`. Add it and try again. If you\'re stuck, try doing `{ctx.prefix}help {command.qualified_name}`.')
    if isinstance(error, commands.BadArgument):
        return await ctx.send(f'Ope! {str(error)}')
    if isinstance(error, FuryException):
        return await ctx.send(f'Ope! {error}')

    tracbeack_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
    log.warning('New error', exc_info=error)
    
    args = []
    for item in ctx.bot.code_chunker(tracbeack_str):
        args.append(item)
        
    await ctx.bot.send_many_to_logging_channel(args=args, kwargs=[])
    

async def setup(bot: FuryBot) -> None:
    bot.add_listener(on_command_error, 'on_command_error')

async def teardown(bot: FuryBot) -> None:
    bot.remove_listener(on_command_error, 'on_command_error')