import enum
import re
import logging
import asyncio
from enum import Enum

import discord
from discord.ext import commands, tasks

import better_profanity
import urlextract

from typing import (
    Union, 
    List, 
    ClassVar, 
    TypedDict,
    Optional
)

from cogs.utils.constants import (
    BYPASS_FURY,
    VALID_GIF_CHANNELS,
    LOCKDOWN_NOTIFICATIONS_ROLE,
    FURY_GUILD,
    NSFW_FILTER_CONSTANT
)
from cogs.utils.errors import NotLocked, AlreadyExtra


def moderator_check(member): 
    return True if BYPASS_FURY in [role.id for role in member.roles] else False

def mention_staff(guild):
    notisRole = discord.utils.get(guild.roles, id=LOCKDOWN_NOTIFICATIONS_ROLE)
    return notisRole.mention

class Reasons(Enum):
    activity = 1
    pfp = 2
    name = 3

class LockedOutInner(TypedDict):
    member_id: int
    bad_status: str
    raw_status: str
    extra: List[Reasons]
    
class LockedOut(TypedDict):
    member_id: LockedOutInner


    
class Events(commands.Cog):
    """
    The base Events cog.
    
    This cog is dedicated to the protection of the server, and maintaining it's "PG" status.
    
    We'll assign each member an entry in the `locked_out` var.
    This will have their id, the reason they were locked, and if they have any extra things to be locked for.
    The extra things will be from the Reasons class.
    
    If a person gets put into the `locked_out` var, the extra section will be empty. If the extra section is not empty
    they can not get unlocked.
    """
    locked_out: ClassVar[LockedOut] = {}
    custom_words: ClassVar[List[str]] = ['chode', 'dick', 'dickandmorty']
    
    def __init__(self, bot):
        self.bot = bot
        self.profanity = better_profanity.profanity

        with open(f"{self.bot.DEFAULT_BASE_PATH}/txt/profanity.txt", 'r') as f:
            extra_profanity = f.readlines()
            extra_profanity = list(dict.fromkeys(extra_profanity))  # clear up duplicates
            extra_profanity += self.custom_words
            self.profanity.add_censor_words(extra_profanity)

        self.extractor = urlextract.URLExtract()
        self.extractor.update()
        
        whitelist = ['omg', 'god', 'lmao']
        for index, string in enumerate(self.profanity.CENSOR_WORDSET): 
            if string._original in whitelist:
                self.profanity.CENSOR_WORDSET.pop(index)

        self.member_check.start()
        
    def cog_unload(self):
        if self.member_check.is_running():
            self.member_check.cancel()
            
    async def contains_profanity(
        self, 
        message: str
    ) -> bool:
        """Verify is a str contains profanity."""
        data = await asyncio.gather(*[self.bot.loop.run_in_executor(None, self.profanity.contains_profanity, message)])
        return data[0] if data else False
    
    async def censor(
        self, 
        message: str
    ) -> str:
        """Censor a str."""
        data = await asyncio.gather(*[self.bot.loop.run_in_executor(None, self.profanity.censor, message)])
        return data[0]
    
    async def get_links(
        self,
        message: str
    ) -> Union[None, List[str]]:
        """Check if a message has link"""
        data = await asyncio.gather(*[self.bot.loop.run_in_executor(None, self.extractor.gen_urls, message)])
        return list(data[0]) if data else None
            
    def is_locked(
        self, 
        member: Union[discord.Member, discord.User, int]
    ) -> bool: 
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member
        return True if self.locked_out.get(member) is not None else False

    def add_extra_for(
        self,
        member: Union[discord.Member, discord.User, int],
        reason: Reasons
    ) -> None:
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member
        if not self.is_locked(member):
            raise NotLocked(f'Member is not locked, could not add extra to their lock data.')
        if reason in self.locked_out[member]['extra']:
            raise AlreadyExtra("Member is already locked out for this reason.")
            
        self.locked_out[member]['extra'].append(reason)
    
    def remove_extra_for(
        self,
        member: Union[discord.Member, discord.User, int],
        reason: Reasons
    ) -> None:
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member      
        try:
            self.locked_out[member]['extra'].remove(reason)
        except ValueError:
            pass
        
    def is_valid_unlock(
        self,
        member: Union[discord.Member, discord.User, int],
        reason: Reasons
    ) -> bool:
        """
        Returns true if the extra section on the users lock data is None.
        """
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member
        
        extra = self.locked_out[member]['extra']
        if not extra: 
            return True
        if len(extra) == 1 and extra[0] == reason:  # The only thing to unlock is the reason we're unlocking.
            self.locked_out[member]['extra'] = []
            return True
        return False
    
    async def handle_roles(
        self, 
        operation: str,
        member: discord.Member, 
        reason: Optional[str] = None, 
        atomic: Optional[bool] = False
    ) -> None:
        attr = getattr(member, operation)
        role = discord.utils.get(member.guild.roles, name='Lockdown')
        return await attr(*[role], reason=reason, atomic=atomic)
    
    async def add_lockdown_for(
        self,
        member: Union[discord.Member, discord.User],
        *,
        enum_reason: Reasons,
        reason: Optional[str] = "Bad status",
        guild: Optional[discord.Guild] = None,
        bad_status: Optional[str] =  None,
        raw_status: Optional[str] = None
    ) -> None:
        """
        Lock a member out for the first time. 
        
        This func can never get called if the member is already locked out.
        """
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        await self.handle_roles('add_roles', member, reason=reason, atomic=False)

        packet = {
            'member_id': member.id,
            'reason': [enum_reason]
        }
        if bad_status:
            packet['bad_status'] = bad_status
        if raw_status:
            packet['raw_status'] = raw_status
        self.locked_out[member.id] = packet
 
        logging.warning(f"ADDED LOCKDOWN: Lockdown added to {str(member)} for: {reason}")
        return
    
    async def remove_lockdown_for(
        self, 
        member: Union[discord.Member, discord.User],
        *,
        guild: Optional[discord.Guild] = None,
        reason: Optional[str] = 'status'
    ) -> discord.Embed:
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        try:
            del self.locked_out[member.id]
        except KeyError:
            raise NotLocked(f'{member.mention} is not locked, can not unlock them')
        
        await self.handle_roles('remove_roles', member, reason=f'Member fixed {reason}', atomic=False)
        
        e = self.bot.Embed()
        
        e.title = 'Thank you.'
        e.description = 'Your lockdown role was removed.'
        try:
            await member.send(embed=e)
            could_dm = True
        except (discord.Forbidden, discord.HTTPException):
            could_dm = False
        
        e.title = "Member fixed their status."
        e.description = f'**{str(member)} ({member.mention})** has fixed their {reason}. Their access to the server has been fixed.'
        e.add_field(name='Could DM?', value=could_dm)
        await self.bot.send_to_log_channel(embed=e, content=mention_staff(member.guild))
        
        logging.info(f"REMOVED LOCKDOWN: Lockdown removed from {str(member)} after fixing their {reason}.")
        return e
    
    async def lockdown_if_necessary_for(
        self,
        member: Union[discord.Member, discord.User],
        *,
        reason: Reasons,
        raw_reason: str = None,
        bad_status: Optional[str] =  None,
        raw_status: Optional[str] = None
    ) -> None:
        if isinstance(member, discord.User):
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        if self.is_locked(member):  # Member is already locked, increment their data.
            return await self.increment_extra_if_necessary_for(member, reason)
        
        # Member is not locked if we get here.
        await self.add_lockdown_for(
            member, 
            enum_reason=reason, 
            reason=raw_reason,
            bad_status=bad_status,
            raw_status=raw_status
        )
    
    async def remove_lockdown_if_necessary_for(
        self,
        member: Union[discord.Member, discord.User],
        reason: Reasons,
        raw_reason: str = None
    ) -> None:
        if isinstance(member, discord.User):
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        if self.is_locked(member):
            if self.is_valid_unlock(member, reason):  # Member has no outstanding locks OR the only lock they have is the one they're getting removed for.
                await self.remove_lockdown_for(member, reason=raw_reason)
            else:  # Member is locked for more then one reason, we need to remove this specific one.
                self.remove_extra_for(member, reason)
                
    async def increment_extra_if_necessary_for(
        self,
        member: Union[discord.Member, discord.User],
        reason: Reasons
    ) -> None:
        data = self.locked_out[member.id]['extra']
        if reason not in data:
            self.locked_out[member.id]['extra'].append(reason)
                
    async def handle_bad_status(
        self, 
        member: discord.Member, 
        activity: discord.CustomActivity
    ) -> discord.Message:
        censored = await self.censor(activity.name)
        
        e = self.bot.Embed()  
        e.title = "Noo!"
        e.description = 'Your status can not contain profanity! I have revoked your access to the server.\n\nFeel this is incorrect? Contact Trevor F.!'
        e.add_field(name='Original activity:', value=activity.name)
        e.add_field(name='Censored', value=censored)
        
        whatToDo = self.bot.Embed(
            title='How to get access back?',
            description='View how to get your access back.'
        )
        whatToDo.add_field(name='Change your status!', value="After you've changed your status I will give you your server perms back again.")
        try:
            await member.send(embed=e)
            await member.send(embed=whatToDo)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            could_dm = False
        
        await self.lockdown_if_necessary_for(
            member, 
            reason=Reasons.activity, 
            raw_reason='status',
            bad_status=censored,
            raw_status=activity.name
        )
        
        e.title = 'Bad status'
        e.description = f'I have detected a bad status on {member.mention}'
        e.add_field(name='Could DM?', value=could_dm)
        
        logging.warning(f"BAD STATUS: Bad status detected on {str(member)}")
        return await self.bot.send_to_log_channel(embed=e, content=mention_staff(member.guild))
    
    async def handle_bad_name(
        self, 
        user: Union[discord.Member, discord.User]
    ) -> None:
        censored = await self.censor(user.name)
        
        e = self.bot.Embed(
            title='Noo!',
            description='Your new name can not contain bad words.\n\n**Because of this I am locking you out of FLVS Fury. To get unlocked change your name to be PG.**'
        )
        e.add_field(name='Name', value=user.name)
        e.add_field(name='Censored', value=censored)
        e.add_field(name='How to get it removed?', value='**Change your Name!**')
        
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
        
    @commands.Cog.listener("on_message")
    async def profanity_filter(
        self, 
        message: discord.Message
    ) -> Union[discord.Message, None]:
        """
        Catch for any profanity sent by users.
        """
        member = message.author
        if not isinstance(member, discord.Member) or member.bot or moderator_check(member):
            return 

        if not await self.contains_profanity(message.clean_content.lower()):  # the member said something fine
            return 
        
        logging.warning(f"PROFANITY FOUND: Profanity found from {str(message.author)}")
        
        await message.delete()

        e = self.bot.Embed(
            title="Noo!",
            description=f"You can't be using that language in this server! You need to remember " \
                "that it is a school discord. Don't say anything here that you wouldn't say in front of your parents or teacher."
        )
        e.set_author(name=str(member), icon_url=member.avatar_url)
        e.add_field(name=f"Original message:", value=message.clean_content)
        e.add_field(name="Clean message:", value=self.profanity.censor(message.clean_content))

        try:
            await member.send(embed=e)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            e.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=e)
            could_dm = False

        logEmbed = self.bot.Embed(
            description=f'**{str(member)}** ({member.mention}) has used terms that contained profanity.\n' \
                f'**Channel:** {message.channel.mention}\n**Member nick:** {member.nick}'
        )
        logEmbed.set_author(name=str(member), icon_url=member.avatar_url)
        logEmbed.add_field(name=f"Original message:", value=message.clean_content)
        logEmbed.add_field(name="Clean message:", value=self.profanity.censor(message.clean_content))
        logEmbed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(content=mention_staff(member.guild), embed=logEmbed)

    @commands.Cog.listener('on_message')
    async def link_checker(
        self, 
        message: discord.Message
    ) -> Union[discord.Message, None]:
        """
        Catch links sent by users. If a link is detected it will be deleted automatically.
        """
        member = message.author
        if not isinstance(member, discord.Member) or member.bot or moderator_check(member):
            return

        urls = await self.get_links(message.clean_content) or re.findall(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            message.clean_content.replace(" ", '')
        )
        if not urls: # No urls within the user's message, do nothing.
            return

        if message.channel.id not in VALID_GIF_CHANNELS:  # The user posted a link in a non-valid channel
            await message.delete()
        else:
            # The user posted a link, but we need to check if it's in a valid channel, and
            # if the link is a valid link.
            
            check = [url for url in urls if re.findall('gifyourgame', url)]  # check for gif your game links
            if not check:  # no gif your game links were sent
                await message.delete()
            elif len(check) != len(urls):  # The user sent a non-valid link alongside a gif your game link, delete it.
                await message.delete()
            else:  
                # We can confirm that all links sent in the users message has gifyourgame in it. 
                # Now we'll check if the channel is valid.
                if message.channel.id not in VALID_GIF_CHANNELS: # The channel is valid, delete message.
                    await message.delete()
                else: 
                    # Everything is ok, do nothing.
                    return

        embed = self.bot.Embed(
            title="Nooo!",
            description=f"We don't use links in this server!"
        )
        embed.add_field(
            name="When can I use links?", 
            value="You can use links when posting from [Gif Your Game](https://www.gifyourgame.com/) in " \
            "any of the game specific general chats. All other links must stay disabled.")
        embed.add_field(name="Links sent:", value=', '.join(urls))

        try:
            await member.send(embed=embed)
            could_dm = True
        except (discord.HTTPException, discord.Forbidden):
            embed.add_field(name="DMs", value="Your DM's are not open, so I was unable to DM you.")
            await message.channel.send(content=member.mention, embed=embed)
            could_dm = False

        embed = self.bot.Embed(
            color=discord.Color.red(), 
            description=f'**{str(member)} ({member.mention})** has sent messages that contain links.',
            title='Links detected')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Links sent:", value=', '.join([f'`{entry}`' for entry in urls]))
        embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(embed=embed)
    
    @commands.Cog.listener('on_member_update')
    async def status_checker(
        self, 
        before: discord.Member,
        member: discord.Member
    ) -> Union[discord.Message, discord.Embed, None]:
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
            return await self.increment_extra_if_necessary_for(member, Reasons.activity)

        if contains_profanity:  # Status contains profanity
            return await self.handle_bad_status(member, activity)
        
        # If we reach here, the members status is A-ok.
        # We'll un-lockdown them if nessecary.
        return await self.remove_lockdown_if_necessary_for(
            member, 
            reason=Reasons.activity, 
            raw_reason='activity'
        )
        
    @commands.Cog.listener('on_user_update')
    async def nsfw_pfp_checker(
        self,
        before: discord.User,
        user: discord.User
    ) -> Union[None, discord.Message]:
        """
        Looks for Nudity and NSFW within a users' pfp. 
        If a NSFW pfp is detected they will be locked and moderators will be noticed.
        """
        if before.avatar == user.avatar: 
            return
        
        params = {
            'url': str(user.avatar_url),
            'models': 'nudity,wad,offensive,text-content,gore',
            'api_user': '35525582',
            'api_secret': self.bot.nsfwAPI
        }
        
        async with self.bot.session.get('https://api.sightengine.com/1.0/check.json', params=params) as resp:
            if resp.status != 200:
                logging.warning("STATUS: Api request status not 200.")
                return
            data = await resp.json()
        
        if any((
            float(data['offensive']['prob']),
            float(data['nudity']['raw']),
            float(data['gore']['prob']),
            float(data['alcohol']),
            float(data['drugs'])
        )) > NSFW_FILTER_CONSTANT:  # Asset is BAD, handle it.
            if self.is_locked(user):  # Member is already locked, add this to the reason of locks.
                return await self.increment_extra_if_necessary_for(user, Reasons.pfp)
        
            logging.warning(f"MEMBER NSFW: {str(user)} has a NSFW pfp, locking them out.")
            
            e = self.bot.Embed()
            e.title = 'NSFW Pfp Detected'
            e.description = "I've detected your new Pfp to be NSFW. Please change it to be unlocked from FLVS Fury."
            e.add_field(name='How to get it removed?', value='**Change your Pfp!**')
            e.add_field(name='Feel this is incorrect?', value='Contact Trevor F. to get it fixed.')
            try:
                await user.send(embed=e)
                could_dm = True
            except (discord.HTTPException, discord.Forbidden):
                could_dm = False
            
            # I do this here because I need it for the mention_staff func.
            # Otherwise, it would happen twice in the lockdown_if_necessary_for func.
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            user = guild.get_user(user.id) or (await guild.fetch_user(user.id))  
            
            await self.lockdown_if_necessary_for(
                user,
                reason=Reasons.pfp,
                raw_reason='pfp'
            )
            
            e.fields[0].name = 'Could DM?'
            e.fields[0].value = could_dm
            e.remove_field(1)
            e.description = f"I've detected a NSFW pfp on {user.mention}"
            return await self.bot.send_to_log_channel(embed=e, content=mention_staff(guild))
        
        
        # If we reach here, the asset is fine.
        return await self.remove_lockdown_if_necessary_for(
            user,
            reason=Reasons.pfp,
            raw_reason='pfp'
        )
                
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
        
        
        if await self.contains_profanity(user.name):  # username is fine.
            return await self.handle_bad_name(user)
        
        return await self.remove_lockdown_if_necessary_for(
            user, 
            reason=Reasons.name, 
            raw_reason='username.'
        )
        
    async def check_for_bad_name(
        self, 
        member: discord.Member
    ) -> None:
        """
        Check for NSFW name on a member. 
        If one is detected then we'll lock them out and alert the user.
        
        This could easily not be a func, but I didn't want to invade on the member_check func too much.
        """
        
        is_locked = self.is_locked(member)
        
        if (await self.contains_profanity(member.name)):
            if is_locked:  # Member was already flagged, do nothing.
                return await self.increment_extra_if_necessary_for(member, Reasons.name)
            return await self.handle_bad_name(member)
        
        # User name is fine
        return await self.remove_lockdown_if_necessary_for(
            member, 
            reason=Reasons.name,
            raw_reason='name'
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


            
        
            
            

def setup(bot):
    bot.add_cog(Events(bot))
