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
    TYPE_CHECKING,
)

import discord
from discord.ext import commands

from .profanity import Profanity
from .core import CoreModeration
from .lockdowns import Lockdowns
from .mutes import Mutes
from .links import Link

from utils import constants
from utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot


class Moderation(
    CoreModeration,
    Lockdowns,
    Mutes,
    Profanity,
    Link,
    brief='Moderation based commands.',
    emoji='\N{HAMMER AND PICK}'
):
    """
    The main Moderation cog. Contains all moderation based commands.
    These commands can only be used by authorized members. If you are not authorized,
    you will be kicked from the server... jokes! :D
    """
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
    
    async def cog_check(self, ctx: Context) -> bool:
        if isinstance(ctx.author, discord.User):
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        
        authorized = (constants.CAPTAIN_ROLE, constants.MOD_ROLE, constants.COACH_ROLE, constants.BYPASS_FURY)
        result = any(r.id in authorized for r in ctx.author.roles)
        if not result:
            raise commands.MissingPermissions(['server_moderator'])
        
        return True
    
    
async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Moderation(bot))
