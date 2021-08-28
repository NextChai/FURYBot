from cogs.utils.types import Reasons
import discord
from discord.ext import commands

from cogs.events.base import BaseEvent
from cogs.utils.constants import GENERAL_CHANNEL


def setup(bot):
    bot.add_cog(OnMemberJoin(bot))


class OnMemberJoin(BaseEvent, command_attrs=dict(hidden=True)):
    __slots__ = ('bot',)
    
    def __init__(self, bot):
        super().__init__(bot)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(GENERAL_CHANNEL)
        
        if await self.contains_profanity(member.name):
            return await self.lockdown_if_necessary_for(member, reason=Reasons.name, raw_reason='Member joined with a bad name')

        e = self.bot.Embed()
        e.title = 'Welcome!'
        e.description = f'Welcome {member.mention}! Check out the info below this line:'
        e.add_field(
            name='Change your nickname!',
            value='Change your server nickname to your **first name last initial!**\nExample: Trevor F.\n\n' \
                'We do this so it is easy for the Coaches to keep track of ya.')
        e.add_field(
            name="Don't know how to change your nickname?",
            value=f'Type any message in the {channel.mention} chat, right click your name, and select "Change Nickname."')
        
        try:
            await member.send(embed=e)
        except:
            await channel.send(embed=e, content=member.mention)
