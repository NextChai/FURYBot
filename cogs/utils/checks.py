import discord
from discord.ext import commands

from cogs.utils.constants import CAPTAIN_ROLE, MOD_ROLE, BYPASS_FURY, COACH_ROLE

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
    roles = [r.id for r in member.roles]
    return BYPASS_FURY in roles