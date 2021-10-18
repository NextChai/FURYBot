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
from os import stat

import re
import sys
import logging
import traceback
import functools
import datetime
from collections import Counter
from typing import Callable, List, Dict, Any, Optional, Union

import asyncio
import aiohttp

import discord
from discord.ext import commands

from urlextract import URLExtract

from cogs.utils.enums import *
from cogs.utils import copy_doc
from cogs.utils import context, constants, checks
from cogs.utils.profanity_filter import CustomProfanity

__all__ = (
    'DiscordBot',
    'Security',
    'Lockdown',
    'SecurityMixin',
    'FuryBot'
)

log = logging.getLogger(__name__)

initial_extensions = (
    'cogs.commands',
    'cogs.moderation',
    'cogs.safety',
    'cogs.owner'
)

@copy_doc(discord.Embed)
def Embed(**kwargs) -> discord.Embed:
    """A method used to have a consistent color across all bot Embeds.
    
    .. note::
        
        This is also so I can change the bots color easily when needed.
    """
    kwargs['color'] = discord.Color.blue()
    return discord.Embed(**kwargs)

class DiscordBot(commands.Bot):
    """The base container for FURY Bot.
    
    Will contain all discord.py related activities and methods.
    
    Fury bot will also have a complete spam detector. This will check for both
    infractions within a certain time frame and a user spamming messages.
    
    Attributes
    ----------
    activity_message: :class:`str`
        The bot's activity message.
    activity_type: :class:`discord.ActivityType`
        The bot's current activity type.
    """
    def __init__(self):
        super().__init__(
            help_command=None,
            description='The Discord bot for the FLVS Fury server.',
            intents=discord.Intents.all(),
            guild_ids=[757664675864248360]
        )
        
        self.Embed: discord.Embed = Embed
        self.activity_message = 'Over the server.'
        self.activity_type = discord.ActivityType.watching
        self.debug: bool = False
        
        for ext in initial_extensions:
            try:
                self.load_extension(ext)
                log.info('Loaded ext: {0}'.format(ext))
            except Exception:
                traceback.print_exc()

    @property
    def activity_message(self) -> str:
        return self._activity_message
    
    @activity_message.setter
    def activity_message(self, message: str) -> None:
        """Set the bots activity and update its message within the Discord API.
        
        .. note::

            This should not be called before the bot is ready.
        
        Parameters
        ----------
        message: :class:`str`
            The message to display.
        
        Returns
        -------
        None
        """
        self._activity_message = message
        self.loop.create_task(self.update_activity())
    
    @property
    def activity_type(self) -> discord.ActivityType:
        return self._activity_type
    
    @activity_type.setter
    def activity_type(self, activity: discord.ActivityType) -> None:
        """Changes the bots activity when a this attr is set.
        
        .. note::

            This should not be called before the bot is ready.
        
        Parameters
        ----------
        activity: :class:`discord.ActivityType`
            The new activity type.
        
        Returns
        -------
        None
        """
        self._activity_type = activity
        self.loop.create_task(self.update_activity())
        
    async def get_context(self, interaction: discord.Interaction, *, cls=context.Context):
        """Used to get context when invoking a command.
        
        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction for the command.
        cls: :class:`context.Context`
            The subclassed context to pass onto the command.
            
        Returns
        --------
        :class:`context.Context`
        """
        return await super().get_context(interaction, cls=cls)
    
    async def send_to_logging_channel(self, *args, **kwargs) -> discord.Mesasage:
        """Send a message to the logging channel.
        
        This is the only non-native dpy related coro. This is so the on_error can get placed here and not
        in the other class.
        
        Parameters
        ----------
        args: List[Any]
            The args to send along to the channel
        kwargs: Dict[Any, Any]
            The kwargs to send along to the channel.
            
        Raises
        ------
        :class:`discord.HTTPException`
            Sending the message failed.
        :class:`discord.Forbidden`
            You do not have the proper permissions to send the message.
        :class:`disord.InvalidArgument`
            The files list is not of the appropriate size, you specified both file and files, or you specified both embed and embeds, or the reference object is not a Message, MessageReference or PartialMessage.
        
        Returns
        -------
        :class:`discord.Message`"""
        channel = self.get_channel(constants.LOGGING_CHANNEL) or (await self.fetch_channel(constants.LOGGING_CHANNEL))
        
        ping_staff = kwargs.pop('ping_staff', True)
        if ping_staff:
            if args:
                content = args[0]
                content = '<@&867901004728762399>\n' + content
            else:
                args = ['<@&867901004728762399>']
                
        return await channel.send(*args, **kwargs)
    
    async def update_activity(self) -> None:
        """Updates the bot's activity to the current set name and type.
        
        Returns
        -------
        None
        """
        await self.wait_until_ready()
        await self.change_presence(activity=discord.Activity(type=self.activity_type, name=self.activity_message))
        
    async def on_ready(self):
        print(f"{self.user.name} has come online.")
        
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """This ensures that Fury bot can't be invited to other discord servers and stay in them.
        
        Returns
        -------
        None
        """
        if guild.id != 757664675864248360:
            await guild.leave()
            
    async def on_error(self, event, *args, **kwargs) -> None:
        """Called when the Bot runs into an error that is not handled by `on_command_error`.
        
        This will print out the error and send it to the logging channel."""
        type, value, traceback_str = sys.exc_info()
        if not type:
            raise

        trace_str = ''.join(traceback.format_exception(type, value, traceback_str))
        print(trace_str)
        await self.send_to_logging_channel(f'```python\n{trace_str}\n```')
        
    async def on_command_error(self, ctx, error) -> None:
        if hasattr(ctx.command, 'on_error'):
            return
        
        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return
            
        e = self.Embed(title='Oh no!')
            
        if isinstance(error, commands.MissingPermissions):
            e.description = 'You do not have the permissions to do this command!'
            return await ctx.send(embed=e)

        if checks.should_ignore(ctx.author) and self.debug:
            exc = getattr(error, 'original', error)
            traceback_str = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__)) # type: ignore
            
            lines = f'Ignoring exception in command {ctx.command}:\n{traceback_str}'
            print(lines)
            
            formatted = lines.replace(traceback_str, f'```python\n{traceback_str}\n```')
            await ctx.send(formatted)
            await self.send_to_logging_channel(formatted)
        else:
            e.description = f'I ran into an error when doing this command!\n\n**{str(error)}**'
            return await ctx.send(embed=e)
        
    async def on_member_lockdown(self, member: discord.Member, reason: Reasons) -> None:
        e = self.Embed(
            title='Member Lockdown',
            description=f'Member {member.mention} has been locked down for {Reasons.type_to_string(reason)}.'
        )
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.set_footer(text=f'Member ID: {member.id}') 
        
        return await self.send_to_logging_channel(embed=e)
    
    async def on_member_freedom(self, member: discord.Member, reason: Reasons) -> None:
        e = self.Embed(
            title='Member Freedom',
            description=f'Member {member.mention} has been freed for {Reasons.type_to_string(reason)}'
        )
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.set_footer(text=f'Member ID: {member.id}') 
        
        return await self.send_to_logging_channel(embed=e)


class Security(CustomProfanity, URLExtract):
    def __init__(self):
        URLExtract.__init__(self)
        super().__init__()
        self.update()
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        
    async def setup_profanity(self) -> None:
        """Used to load the wordsets of the profanity filter.
        
        .. note::
            
            This is not done in the ProfanityFilter class because 
            I didn't want to pass in the bots loop.
        """
        await self.load_dirty_words()
        await self.load_clean_words()
        
    async def wrap(self, method: Callable, *args, **kwargs):
        """A utility coro used to wrap a blocking call in a `run_in_executor` to not block the bot."""
        wrapped = functools.partial(method, *args, **kwargs)
        return await self.loop.run_in_executor(None, wrapped)
    
    async def contains_profanity(self, message: str) -> bool:
        """Used to determine if a message has profanity.
        
        Parameters
        ----------
        message: :class:`str`
            The message to check.
        
        Returns
        -------
        :class:`bool`
        """
        return await self.wrap(self.has_bad_word, message)
    
    async def censor_message(self, message: str) -> str:
        """Used to censor a message.
        
        Parameters
        ----------
        message: :class:`str`
            The message to censor.
        
        Returns
        -------
        :class:`str`
            The message that was censored
        """
        return await self.wrap(self.censor, message)
    
    async def get_links(self, message: str) -> List[str]:
        """Extreact links from a certain message.
        
        Parameters
        ----------
        message: :class:`str`
            The message to extract URL's from.
        
        Returns
        -------
        List[:class:`str`]
            The list of url's extracted from a message.
        """
        links = await self.wrap(self.find_urls, message)
        if not links:
            links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
        return links
    
    async def contains_links(self, message: str) -> bool:
        """Determine if a message contains links.
        
        .. note:
            
            Returns the bool value from :meth:`Security.get_links`
            
        Parameters
        ----------
        message: :class:`str`
            The message to determine.
            
        Returns
        -------
        :class:`bool`
        """
        links = await self.get_links(message)
        if not links:
            links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
            if not links:
                return False
            
        return links != []
    
    async def is_valid_link(self, link: str) -> bool:
        """Determine if a link is valid.
        
        .. note::
            
            Valid means any link that is from `gifyourgame`, `streambale`, or `lowkey.gg` and in a valid gif channel.
            
        Parameters
        ----------
        link: :class:`str`
            The link to check.
        channel: Optional[:class:`discord.Guild.Channel`]
            Pass in a channel to determine if the link is in a valid gif channel.
        """
        check = await self.wrap(re.findall, r'gifyourgame|streamable|lowkey.gg|smash.gg|app.playvs.com', link)
        if not check:
            return False
        return True
    
    async def get_nsfw(self, url: str) -> Dict:
        """Get NSFW data from the local api to determine if an image is NSFW.
        
        Parameters
        ----------
        url: :class:`str`
            The image to use.
        
        Returns
        -------
        Dict
        """
        async with self.session.get(url='http://localhost:8000/', params={'url': url}) as resp:
            return await resp.json()
        
    async def is_nsfw(self, url: str) -> bool:
        data = await self.get_nsfw(url)
        return data['data']['is_nsfw']
        
        
class Lockdown:
    """The Lockdown implementation of the bot.
    
    This will manage all lockdown based methods and handle unlocking.
    
    Attributes
    ----------
    locked_out: Dict[:class:`int`, Dict[:class:`str`, List[Any]]]
        The locked out members and their corresponding data.
    """
    def __init__(self):
        self.locked_out: Dict[int, Dict[str, List[Any]]] = {}
    
    @staticmethod
    def get_lockdown_role(guild: discord.Guild):
        return guild.get_role(constants.LOCKDOWN_ROLE)

    def get_lockdown_info(self, member: Union[discord.Member, discord.User]) -> Optional[Dict]:
        """A method used to get the lockdown info from a member.
        
        Parameters
        ----------
        member: Union[:class:`discord.Member`, :class:`discord.User`]
            The member to get lockdown info from.
            
        Returns
        -------
        Optional[Dict]
        """
        return self.locked_out.get(member.id)
    
    def is_locked(self, member: Union[discord.Member, discord.User]) -> bool:
        """Determine if a member is locked.
        
        Parameters
        ----------
        member: Union[:class:`discord.Member`, :class:`discord.User`]
            The member to check.
            
        Returns
        -------
        :class:`bool`
        """
        return self.get_lockdown_info(member) is not None
    
    async def send_to(self, member: discord.Member, *args, **kwargs) -> Optional[discord.Message]:
        """Neatly sends a message to a member. Any exceptions thrown will be quietly handled.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to send to.
        args: List[Any]
            The args to pass along to the send function.
        kwargs: Dict[Any, Any]
            The args to pass along to the send function.
        
        Returns
        -------
        Optional[:class:`discord.Message`]
            The message returned from sending to the member. Is none if sending failed.
        """
        try:
            await member.send(*args, **kwargs)
        except (discord.HTTPException, discord.Forbidden):
            return None
        
    async def lockdown(self, member: discord.Member, *, reason: Reasons) -> bool:
        """Adds a user to Lockdown.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to Lockdown.
        reason: :class:`Reasons`
            The reason for locking down the member.
            
        Returns
        -------
        :class:`bool`
            Tells you if the member's Lockdown role is new. 
                - True = lockdown is new
                - False = the user's lockdown has been extended for another reason.
        """
        log.info(f'Coro lockdown was called on {member} for reason {Reasons.type_to_string(reason)}')
        
        placeholder = self.locked_out.get(member.id)
        if placeholder is not None:
            self.locked_out[member.id]['reasons'].append(reason)
            return False
        
        self.locked_out[member.id] = {}
        
        current = self.locked_out[member.id]
        current['roles'] = [role.id for role in member.roles]
        current['reasons'] = [reason]
        
        lr = self.get_lockdown_role(member.guild)

        await member.edit(roles=[lr], reason='Member is getting locked down.')
        
        e = Embed(
            title='Oh no!',
            description=f'You have been given the **Lockdown** role in the FLVS Fury server!'
        )
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.set_footer(text=f'Member ID: {member.id}') 
        
        e.add_field(name='What does this mean?', value='You no longer have access to the server for now!')
        
        reasons = ', '.join([f'**{Reasons.type_to_string(reason)}**' for reason in current['reasons']])
        e.add_field(name='Why am I locked down?', value=f'Locked down for: {reasons}')
        
        await self.send_to(member, embed=e)
        return True
        
    async def freedom(self, member: discord.Member, *, reason: Reasons) -> bool:
        """Removes a users lockdown state and restores their original roles.
        
        .. note::   
        
            This will not remove the members lockdown if the user has other outstanding lockdown reasons.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to free from lockdown.
        reason: :class:`Reasons`
            The reason for unlocking the member.
            
        Returns
        -------
        :class:`bool`
            Whether or not the unlock was successful.
        """
        log.info(f'Coro freedom called on {member} for {Reasons.type_to_string(reason)}')
        
        current = self.locked_out.get(member.id)
        if current is None:
            return False 
        
        self.locked_out.pop(member.id)
        
        current['reasons'].remove(reason)
        
        if current['reasons']:
            return False
        
        roles = []
        for id in current['roles']:
            role = member.guild.get_role(id) or discord.utils.get(member.guild.roles, id=id)
            if role is not None:
                roles.append(role)

        if roles:
            await member.edit(roles=roles, reason='Member freedom.')
        
        e = Embed(
            title='Oh yea!',
            description=f'You have been unlocked from {member.guild.name}!'
        )
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        e.set_footer(text=f'Member ID: {member.id}') 
        
        await self.send_to(member, embed=e)
        return True
        
    async def lockdown_for(self, seconds: Union[int, float], *, member: discord.Member, reason: Reasons) -> None:
        """Lockdown a member for a specific amount of time.
        
        .. note::
            
            This is lazily done, if the bot goes offline 
            the person will NOT get unlocked.
            
        Parameters
        ----------
        seconds: Union[:class:`int`, :class:`float`]
            The total amount of seconds to lock down the member for.
        member: :class:`discord.Member`
            The member to lockdown.
        reason: :class:`Reasons`
            The reason for locking down the member.
        
        Returns
        -------
        None
        """
        await self.lockdown(member, reason=reason)
        await asyncio.sleep(int(seconds))
        await self.freedom(member, reason=reason)

    async def lockdown_until(self, time: datetime.datetime, *, member: discord.Member, reason: Reasons):
        """Lockdown a member until a specific time.
        
        Parameters
        ----------
        time: :class:`datetime.datetime`
            The time to unlock the member.
        member: :class:`discord.Member`
            The member to lockdown.
        reason: :class:`Reasons`
            The reason for locking down the member.
        """
        now = datetime.datetime.utcnow()
        form = (now - time) if now > time else (time - now)
        total_seconds = form.total_seconds()
        
        await self.lockdown_for(total_seconds, member=member, reason=reason)
        
        
class SecurityMixin(Security, Lockdown):
    """A mixin that implements the attrs and methods of both the 
    Lockdown and Secury classes into one.
    
    This will be used to inherit onto FuryBot, the main the bot class."""
    def __init__(self):
        Lockdown.__init__(self)
        super().__init__()
        
                 
class FuryBot(DiscordBot, SecurityMixin):
    """The actual implmentation of Fury Bot. This is where we'll
    keep all guild-specific related items.
    
    Attributes
    ----------
    locked_out: Dict[:class:`int`, Dict[Any, Any]]
        The locked out dict of members.
    Embed: :class:`discord.Embed`
        The base embed for the bot.
        
        ..note::

            Attribute is a callable.
    activity_message: :class:`str`
        The activitiy message for the bot. When this gets updated the activity will change as well.
        
        .. note::   

            This has been wrapped in `create_task`
    activity_type: :class:`discord.ActivityType`
        The type of activity for the bot. When this gets updated the activity will change as well.
        
        .. note::   

            This has been wrapped in `create_task`
    debug: :class:`bool`
        Whether or not the bot is in "Debug mode". This will spit back
        raw errors to qualified users.
    session: :class:`aiohttp.ClientSession`
        The bot's session to use for http requests.
    """
    def __init__(self):
        SecurityMixin.__init__(self)
        super().__init__()

    async def lockdown(self, member: discord.Member, *, reason: Reasons) -> bool:
        self.dispatch('member_lockdown', member, reason)
        return await super().lockdown(member, reason=reason)
    
    async def freedom(self, member: discord.Member, *, reason: Reasons) -> bool:
        self.dispatch('member_freedom', member, reason)
        return await super().freedom(member, reason=reason)