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
        
    @commands.slash(
        name='ping',
        description='Ping the bot to ensure it is online.',
    )
    async def ping(self, ctx: Context):
        """A simple ping slash command.
        
        Used to determine if the bot has been heartbeat blocked by some bad code.
        
        Parameters
        ----------
        None
        """
        return await ctx.send(f"Pong! {ceil(round(self.bot.latency * 1000))} ms.")
    
    @commands.slash(
        name='wave',
        description='Wave to a message',
        type=commands.InteractionType.user
    )
    async def wave(self, ctx: Context):
        """A simple command that allows users to wave to a user via a User based Application Command.
        
        Parameters
        ----------
        None
        
        Returns
        ------
        None
        """
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
        """Created to users can report issues related to the bot, other members, or anyhting else related to it.
        
        Parameters
        ---------
        message: :class:`str`
            The message the user would like to report.
        """
        e = self.bot.Embed(
            title=f'Report from {ctx.author}',
            description=f'{ctx.author.mention} used the report command in {ctx.channel.mention}'
        )
        e.add_field(name='Message', value=message)
        await self.bot.send_to_logging_channel('<@!146348630926819328>', embed=e, view=ReportView(ctx.channel.id), ping_staff=False)
        
        return await ctx.send("I've reported this issue, you should get a response back from Trevor F. soon, thank you!", ephemeral=True)
        
        
def setup(bot):
    bot.add_cog(Commands(bot))