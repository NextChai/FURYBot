import re
import logging
import asyncio

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
    FURY_GUILD
)

NSFW_FILTER_CONSTANT = 0.3


class LockedOut(TypedDict):
    member_id: int
    bad_status: str
    raw_status: str

def moderator_check(member): 
    return True if BYPASS_FURY in [role.id for role in member.roles] else False

def mention_staff(guild):
    notisRole = discord.utils.get(guild.roles, id=LOCKDOWN_NOTIFICATIONS_ROLE)
    return notisRole.mention

    
class Events(commands.Cog):
    locked_out: ClassVar[LockedOut] = {}
    custom_words: ClassVar[List[str]] = ['chode']
    
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
            
    def is_locked(self, member):   # This can easily be a var but I want it as a method
        return True if self.locked_out.get(member.id) is not None else False
    
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
        
        await message.delete(reason='Profanity found')

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
        if not urls:  # no urls in message, run a second check
            return

        if message.channel.id not in VALID_GIF_CHANNELS:  # the user isn't allowed to post links in not main chats
            await message.delete()
        else:
            check = [url for url in urls if re.findall('gifyourgame', url)]  # check for gif your game
            if not check:  # no gif your game messages
                await message.delete()
            else:  # all links are gif your game
                if message.channel.id not in VALID_GIF_CHANNELS:  # channel is not valid
                    await message.delete()
                else:
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

        embed = discord.Embed(color=discord.Color.red(), title=f'**{str(member)} ({member.mention})** has sent messages that contain links.')
        embed.add_field(name=f"Original message:", value=message.clean_content)
        embed.add_field(name="Links sent:", value=', '.join([f'`{entry}`' for entry in urls]))
        embed.add_field(name="Could DM member:", value=str(could_dm))
        return await self.bot.send_to_log_channel(embed=embed)
    
    async def handle_roles(
        self, 
        operation: str,
        member: discord.Member, 
        reason: str = None, 
        atomic: bool = False
    ) -> None:
        attr = getattr(member, operation)
        role = discord.utils.get(member.guild.roles, name='Lockdown')
        return await attr(*[role], reason=reason, atomic=atomic)
    
    async def remove_lockdown_for(
        self, 
        member: Union[discord.Member, discord.User],
        *,
        guild: Optional[discord.Guild] = None,
        reason: Optional[str] = 'status'
    ) -> discord.Embed:
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        del self.locked_out[member.id]
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
    
    async def add_lockdown_for(
        self,
        member: Union[discord.Member, discord.User],
        *,
        reason: Optional[str] = "Bad status",
        guild: Optional[discord.Guild] = None,
        bad_status: Optional[str] =  None,
        raw_status: Optional[str] = None
    ) -> None:
        logging.info(f"ADDED LOCKDOWN: Lockdown added to {str(member)} for: {reason}")
        
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))
        
        await self.handle_roles('add_roles', member, reason=reason, atomic=False)
        
        self.locked_out[member.id] = {
            'member_id': member.id,
            'bad_status': bad_status,
            'raw_status': raw_status
        }
        return
    
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
            
        await self.add_lockdown_for(member, bad_status=censored, raw_status=activity.name)
        
        e.title = 'Bad status'
        e.description = f'I have detected a bad status on {member.mention}'
        e.add_field(name='Could DM?', value=could_dm)
        return await self.bot.send_to_log_channel(embed=e, content=mention_staff(member.guild))
    
    @commands.Cog.listener('on_member_update')
    async def status_checker(
        self, 
        before: discord.Member,
        member: discord.Member
    ) -> Union[discord.Message, discord.Embed, None]:
        """
        Check users status' as they update. 
        
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
            if self.is_locked(member):
                return await self.remove_lockdown_for(member)
            return

        # If we reach here, the member is online and they have an activity.
        # We'll check for profanity and go from there.
        activity = activities[0]
        
        if not activity.name:  # Member can have only an emoji as their status
            if self.is_locked(member):
                return await self.remove_lockdown_for(member)
            return
        
        contains_profanity = await self.contains_profanity(activity.name)
        
        if contains_profanity and self.is_locked(member):
            return
        
        # The Member was online and did not switch during the before and after
        # The Member has a status
        if contains_profanity:  # Status contains profanity
            return await self.handle_bad_status(member, activity)
        
        # If we reach here, the members status is A-ok.
        # We'll un-lockdown them if nessecary.
        if self.is_locked(member):
            return await self.remove_lockdown_for(member)
        return
    
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
            logging.info("USER AVATAR IS THE SAME")
            return
        
        logging.info(f'MEMBER AVATAR UPDATE')

        params = {
            'url': str(user.avatar_url),
            'models': 'nudity,wad,offensive,text-content,gore',
            'api_user': '35525582',
            'api_secret': self.bot.nsfwAPI
        }
        
        async with self.bot.session.get('https://api.sightengine.com/1.0/check.json', params=params) as resp:
            if resp.status != 200:
                logging.info("STATUS IS NOT 200.")
                return
            
            data = await resp.json()
            from pprint import pprint
            pprint(data)
        
        if any((
            float(data['offensive']['prob']),
            float(data['nudity']['raw']),
            float(data['gore']['prob']),
            float(data['alcohol']),
            float(data['drugs'])
        )) > NSFW_FILTER_CONSTANT:  # Asset is BAD, handle it.
            if self.is_locked(user):  # Member is already locked, do nothing.
                return
        
            logging.info(f"MEMBER NSFW: {str(user)} has a NSFW pfp, locking them out.")
            
            e = self.bot.Embed()
            e.title = 'NSFW Pfp Detected'
            e.description = "I've detected your new Pfp to be NSFW. Please change it to be unlocked from FLVS Fury."
            e.add_field(name='How to get it removed?', value='**Change your Pfp!**')
            e.add_field(name='Feel this is incorrect?', value='Contact Trevor F. to get it fixed.')
            try:
                await user.send(embed=e)
                could_dm = True
            except:
                could_dm = False
            
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            await self.add_lockdown_for(user, reason='Bad PFP, NSFW', guild=guild)
            
            e.remove_field(1)
            e.fields[0].name = 'Could DM?'
            e.fields[0].value = could_dm
            e.description = f"I've detected a NSFW pfp on {user.mention}"
            return await self.bot.send_to_log_channel(embed=e, content=mention_staff())
        
        
        # If we reach here, the asset is fine.
        if self.is_locked(user):  # User is locked, remove it.
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            await self.remove_lockdown_for(user, guild=guild, reason='pfp')
         
        
    @tasks.loop(count=1)
    async def member_check(self) -> None:
        """
        Check for bad status' upon loading. If the status is bad,
        """
        guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
        
        ignored = (discord.Spotify, discord.Activity, discord.Game, discord.Streaming)
        async for member in guild.fetch_members(limit=None):
            for activity in member.activities:
                if isinstance(activity, ignored) or not activity.name: continue  # ONE LINER WOOO
                if not (await self.contains_profanity(activity.name)): continue
                
                logging.info(f"BAD STATUS: Bad status detected on {str(member)}")
                await self.handle_bad_status(member, activity)
    
    @member_check.before_loop   
    async def before_loop(self):
        logging.info("TASK WAIT: Waiting for member_check inside of events.py")
        await self.bot.wait_until_ready()


            
        
            
            

def setup(bot):
    bot.add_cog(Events(bot))
