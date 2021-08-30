from cogs.utils.types import Reasons
import discord
from discord.ext import commands

from cogs.events.base import BaseEvent
from cogs.utils.constants import GENERAL_CHANNEL

from datetime import datetime, timedelta


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
        
        thursday = datetime(year=2021, month=9, day=2, hour=14, minute=0, second=0)
        four = thursday + timedelta(days=0, hours=23)
        fourthirty = four + timedelta(minutes=30)
        five = four + timedelta(hours=1)
        six = five  + timedelta(hours=1)
        
        e.add_field(
            name='eSports Meetings!',
            value=f'If you are 13+ years of age we have eSports meetings this Thursday the 2nd and Friday the 3rd.' \
                f'**Thursday:**\n**{discord.utils.format_dt(thursday)}:** Quick meeting about info with eSports.\n\n' \
                    '**Friday:**\n' \
                    f'**{discord.utils.format_dt(four)} (30 mins long)** Super Smash Players' \
                    f'\n**{discord.utils.format_dt(fourthirty)} (30 mins long)** League of Legends Players' \
                    f'\n**{discord.utils.format_dt(five)}** (1 hour long) Overwatch and Fortnite players' \
                    f'\n**{discord.utils.format_dt(six)}:** (30 mins long) Rocket League Players'
        )
        
        try:
            await member.send(embed=e)
        except:
            await channel.send(embed=e, content=member.mention)
