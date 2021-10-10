from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'ReportView',
    'Commands',
)

class JumpButton(discord.ui.Button):
    def __init__(self, channel_id):
        self.channel_id = channel_id
        super().__init__(style=discord.ButtonStyle.green, label='Jump!')
        
    async def callback(self, interaction: discord.Interaction):
        return await interaction.response.send_message(f'<#{self.channel_id}>', ephemeral=True)
    

class ReportView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=3600)
        self.add_item(JumpButton(channel_id))
        

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
        
    @commands.slash(
        name='report',
        description='Report a bug!',
        options=[
            commands.CommandOption(
                name='message',
                description='The message to report',
                required=True
            )
        ]
    )
    @commands.guild_only()
    async def report(self, ctx: Context, message: str):
        e = self.bot.Embed(
            title=f'Report from {ctx.author}',
            description=f'{ctx.author.mention} used the report command in {ctx.channel.mention}'
        )
        e.add_field(name='Message', value=message)
        await self.bot.send_to_logging_channel('<@!146348630926819328>', embed=e, view=ReportView(ctx.channel.id), ping_staff=False)
        
        return await ctx.send("I've reported this issue, you should get a response back from Trevor F. soon, thank you!", ephemeral=True)
        
        
def setup(bot):
    bot.add_cog(Commands(bot))