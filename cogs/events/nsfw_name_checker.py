import logging
from typing import Optional, Union

import discord
from discord.ext import commands, tasks

from cogs.events.base import BaseEvent, mention_staff
from cogs.utils.types import Reasons
from cogs.utils.constants import FURY_GUILD

def setup(bot):
    bot.add_cog(NsfwNameChecker(bot))


class NsfwNameChecker(BaseEvent, command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        super().__init__(bot)
        self.member_check.start()
        
    def cog_unload(self):
        if self.member_check.is_running():
            self.member_check.stop()
        
    async def check_for_bad_name(self, member: discord.Member) -> None:
        """
        Check for NSFW name on a member. 
        If one is detected then we'll lock them out and alert the user.
        
        This could easily not be a func, but I didn't want to invade on the member_check func too much.
        """
        
        is_locked = self.is_locked(member)
        
        if (await self.contains_profanity(member.name)):
            if is_locked:  # Member was already flagged, do nothing.
                return self.increment_extra_if_necessary_for(member, Reasons.name)
            return await self.handle_bad_name(member)
        
        # User name is fine
        await self.remove_lockdown_if_necessary_for(
            member, 
            reason=Reasons.name,
            raw_reason='name'
        )
        
    async def handle_bad_name(
        self, 
        user: Union[discord.Member, discord.User]
    ) -> None:
        is_nick = False
        censored = await self.censor(user.name)
        if censored == user.name:
            if isinstance(user, discord.Member):
                censored = await self.censor(user.nick)
                is_nick = True
        
        e = self.bot.Embed(
            title='Noo!',
            description='Your new name can not contain bad words.\n\n**Because of this I am locking you out of FLVS Fury. To get unlocked change your name to be PG.**'
        )
        e.add_field(name='Name', value=user.name)
        e.add_field(name='Censored', value=censored)
        
        formatted = 'Name' if not is_nick else 'Nickname'
        e.add_field(name='How to get it removed?', value=f'**Change your {formatted}!**')
        
        try:
            await user.send(embed=e)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            could_dm = False
        
        modEmbed = self.bot.Embed(
            title="Profanity Name",
            description=f"{str(user)}'s {(user.mention)} name contains profanity. I've locked them out from the server."
        )
        modEmbed.add_field(name='Could DM', value=could_dm)
        
        if isinstance(user, discord.User):
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            user = guild.get_member(user.id) or (await guild.fetch_member(user.id))
        else:
            guild = user.guild
            
        logging.warning(f"BAD NAME: {str(user)} has a name that contains profanity.")
        
        await self.lockdown_if_necessary_for(
            user,
            reason=Reasons.name,
            raw_reason='name',
            bad_status=censored,
            raw_status=user.name,
        )
        await self.bot.send_to_log_channel(content=mention_staff(guild), embed=modEmbed)
        
    @commands.Cog.listener('on_user_update')
    async def nsfw_name_checker(
        self,
        before: discord.User,
        user: discord.User
    ) -> Union[None, discord.Message]:
        """
        When a user updates their name check for it containing NSFW. If it contains NSFW Lock the user out.
        """
        if before.name == user.name: return
        
        
        if (await self.contains_profanity(user.name)):  # username is NOT fine.
            return await self.handle_bad_name(user)
        
        return await self.remove_lockdown_if_necessary_for(
            user, 
            reason=Reasons.name, 
            raw_reason='username.'
        )
        
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> Optional[discord.Message]:
        if before.nick == after.nick: return
        
        if (await self.contains_profanity(after.nick)):  # username is NOT fine.
            return await self.handle_bad_name(after)
        
        return await self.remove_lockdown_if_necessary_for(
            after, 
            reason=Reasons.name, 
            raw_reason='username.'
        )

    @tasks.loop(count=1)
    async def member_check(self) -> None:
        """
        Check for bad status upon loading. If the status is bad, lock them out.
        """
        guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
        
        ignored = (discord.Spotify, discord.Activity, discord.Game, discord.Streaming)
        async for member in guild.fetch_members(limit=None):
            # Member check for bad name before anything else
            await self.check_for_bad_name(member)
            
            activity = [activity for activity in member.activities if not isinstance(activity, ignored)]
            if not activity:
                continue
            
            activity = activity[0]
            if not (await self.contains_profanity(activity.name)): continue
            
            await self.handle_bad_status(member, activity)
    
    @member_check.before_loop   
    async def before_loop(self):
        logging.info("TASK WAIT: Waiting for member_check inside of events.py")
        await self.bot.wait_until_ready()