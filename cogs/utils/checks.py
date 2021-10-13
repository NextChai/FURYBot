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

import discord
from discord.ext import commands

from cogs.utils.constants import CAPTAIN_ROLE, MOD_ROLE, BYPASS_FURY, COACH_ROLE

__all__ = (
    'is_captain',
    'is_mod',
    'is_coach',
    'should_ignore',
)

def is_captain():
    async def predicate(ctx):
        roles = [r.id for r in ctx.author.roles]
        return CAPTAIN_ROLE in roles
    return commands.check(predicate)

def is_mod():
    async def predicate(ctx):
        roles = [r.id for r in ctx.author.roles]
        return MOD_ROLE in roles
    return commands.check(predicate)

def is_coach():
    async def predicate(ctx):
        roles = [r.id for r in ctx.author.roles]
        return COACH_ROLE in roles
    return commands.check(predicate)
        
def should_ignore(member: discord.Member) -> bool:
    """Determines if Fury Bot should ignore this member for Security"""
    if not isinstance(member, discord.Member):
        return False
    
    roles = [r.id for r in member.roles]
    return BYPASS_FURY in roles or member.bot