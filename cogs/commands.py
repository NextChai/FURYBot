from __future__ import annotations

import discord
from discord.ext import commands

from typing import TYPE_CHECKING
from math import ceil

if TYPE_CHECKING:
    from bot import FuryBot

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot
        
    @commands.slash(
        name='ping',
        description='Ping the bot to ensure it is online.',
    )
    async def ping(self, ctx):
        return await ctx.send(f"Pong! {ceil(round(self.bot.latency * 1000))} ms.")
    
    @commands.slash(
        name='wave',
        description='Wave to a message',
        type=commands.InteractionType.user
    )
    async def wave(self, ctx):
        await ctx.send("👋")
        
def setup(bot):
    bot.add_cog(Commands(bot))