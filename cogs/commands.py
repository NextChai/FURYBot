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

import json
from math import ceil
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.utils.context import Context
from .utils.time import human_time

if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'ReportView',
    'Commands',
)


class JumpButton(discord.ui.Button):
    """Used to handle the interaciton given when the "Jump!" button is pressed
    in the ReportView.
    
    Attributes
    ----------
    channel_id: :class:`int`
        The channel id of the report command.
    """
    __all__ = ('channel_id',)
    
    def __init__(self, channel_id):
        self.channel_id = channel_id
        super().__init__(style=discord.ButtonStyle.green, label='Jump!')
        
    async def callback(self, interaction: discord.Interaction):
        """Called when the button has been interacted with.
        
        .. note::
            
            The button has to be pressed within 1 hour of the message being sent.
            
        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that gets tagged along with this button.
        
        Returns
        ------
        None
        """
        return await interaction.response.send_message(f'<#{self.channel_id}>', ephemeral=True)
    

class ReportView(discord.ui.View):
    """Passed onto :meth:`Context.send` in the `report` command.
    
    .. note::
        
        This is not locked, meaning any person who has access to the channel in which this button is called
        can press it.
    """
    __slots__ = ()
    
    def __init__(self, channel_id):
        super().__init__(timeout=3600)
        self.add_item(JumpButton(channel_id))
        

class Commands(commands.Cog):
    """The base Commands cog for the bot.
    
    .. note::
        
        Any user in the server is allowed to use these commands.
        
    .. note::

        Commands will not have the :class:`Context` parameter filled in the Parameters section.
        This is because the ctx parameter is not a required one for the user.
        
    Attributes
    ----------
    bot: :class:`FuryBot`
        The main bot.
    """
    def __init__(self, bot):
        self.bot: FuryBot = bot

    @commands.slash(name='ping', description='Ping the bot to ensure it is online.',)
    async def ping(self, ctx: Context):
        return await ctx.send(f"Pong! {ceil(round(self.bot.latency * 1000))} ms.")
    
    @commands.message()
    async def wave(self, ctx: Context):
        await ctx.send("👋")
        
    @commands.message(name='raw')
    async def raw_message(self, ctx: Context):
        message = await self.bot.http.get_message(ctx.channel.id, ctx.target.id)
        post = await self.bot.post_to_mystbin(json.dumps(message, indent=4), syntax='json')
        return await ctx.send(f'Raw message: <{post}>')
    
    @commands.user(name='raw')
    async def raw_user(self, ctx: Context):
        member = await self.bot.http.get_member(ctx.guild.id, ctx.target.id)
        post = await self.bot.post_to_mystbin(json.dumps(member, indent=4), syntax='json')
        return await ctx.send(f'Raw member: <{post}>')
        
    @commands.slash(name='report', description='Report a bug!')
    @commands.guild_only()
    @commands.describe('message', description='The message to report')
    async def report(self, ctx: Context, message: str):
        e = self.bot.Embed(
            title=f'Report from {ctx.author}',
            description=f'{ctx.author.mention} used the report command in {ctx.channel.mention}'
        )
        e.add_field(name='Message', value=message)
        await self.bot.send_to_logging_channel('<@!146348630926819328>', embed=e, view=ReportView(ctx.channel.id))
        
        return await ctx.send("I've reported this issue, you should get a response back from Trevor F. soon, thank you!", ephemeral=True)
    
    @commands.slash(name='uptime', description='Get the uptime of the bot.')
    async def uptime(self, ctx: Context) -> None:
        return await ctx.send(f'The bot has been online for {human_time(self.bot.start_time)}')
    
        
def setup(bot):
    return bot.add_cog(Commands(bot))