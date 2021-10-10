from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import FuryBot
    from cogs.utils.context import Context
    
__all__ = (
    'Commands',
)


class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot
        
    @commands.slash(
        name='ping',
        description='Ping the bot to ensure it is online.',
    )
    async def ping(self, ctx: Context):
        return await ctx.send(f"Pong! {ceil(round(self.bot.latency * 1000))} ms.")
    
    @commands.slash(
        name='wave',
        description='Wave to a message',
        type=commands.InteractionType.user
    )
    async def wave(self, ctx: Context):
        await ctx.send("👋")
        
def setup(bot):
    bot.add_cog(Commands(bot))