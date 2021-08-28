from typing import Union

import discord
from discord.ext import commands

from cogs.events.base import BaseEvent

from cogs.utils.types import Reasons

def setup(bot):
    bot.add_cog(StatusChecker(bot))


class StatusChecker(BaseEvent, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        super().__init__(bot)
        
    @commands.Cog.listener('on_member_update')
    async def status_checker(self, before: discord.Member, member: discord.Member) -> Union[discord.Message, discord.Embed, None]:
        """
        Check users status as they update. 
        
        If a status is not "PG", they will be locked down and the staff will be alerted. Once the status is cleared,
        their access to the server will be fixed.
        """
        if before.activities == member.activities: return
        
        ignored = (discord.Spotify, discord.Activity, discord.Game, discord.Streaming)
        activities = [activity for activity in member.activities if not isinstance(activity, ignored)]
        
        status = discord.Status
        if member.status == status.offline:
            # When a member goes offline, they can't have a status.
            # Because of this, if a member is locked down they could go into offline to get around it.
            # This accounts for that.
            return None
        
        if not activities:  # all activities were taken away, they can't have a bad activity
            return await self.remove_lockdown_if_necessary_for(
                member, 
                reason=Reasons.activity, 
                raw_reason='activity'
            )

        # If we reach here, the member is online and they have an activity.
        # We'll check for profanity and go from there.
        activity = activities[0]
        
        if not activity.name:  # Member can have only an emoji as their status
            return await self.remove_lockdown_if_necessary_for(
                member, 
                reason=Reasons.activity, 
                raw_reason='activity'
            )
        
        contains_profanity = await self.contains_profanity(activity.name)
        
        if contains_profanity and self.is_locked(member):  # Has profanity and is already locked, increment extra
            return self.increment_extra_if_necessary_for(member, Reasons.activity)

        if contains_profanity:  # Status contains profanity
            return await self.handle_bad_status(member, activity)
        
        # If we reach here, the members status is A-ok.
        # We'll un-lockdown them if nessecary.
        return await self.remove_lockdown_if_necessary_for(
            member, 
            reason=Reasons.activity, 
            raw_reason='activity'
        )
        