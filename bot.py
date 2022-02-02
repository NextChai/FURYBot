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

import re
import sys
import json
import logging
import traceback
import functools
import datetime
import contextlib
from typing import TYPE_CHECKING, Callable, List, Dict, Optional, Union, Coroutine, Any

import aiohttp
import mystbin
import asyncpg

import discord
from discord.ext import commands
from discord.embeds import EmptyEmbed

from urlextract import URLExtract

from cogs.utils.enums import *
from cogs.utils import copy_doc
from cogs.utils import context, constants, checks
from cogs.utils.profanity_filter import CustomProfanity
from cogs.utils.timer import TimerHandler
from cogs.utils.time import UserFriendlyTime, human_time
from config import postgresql as uri, logging_webhook, message_webhook

__all__ = (
    'DiscordBot',
    'Security',
    'Lockdown',
    'SecurityMixin',
    'FuryBot',
)

log = logging.getLogger(__name__)

MISSING = discord.utils.MISSING

initial_extensions = (
    'cogs.commands',
    'cogs.moderation',
    'cogs.safety',
    'cogs.owner'
)

@copy_doc(discord.Embed)
def Embed(
    *,
    title: str = EmptyEmbed,
    description: str = EmptyEmbed,
    url: str = EmptyEmbed,
    timestamp: datetime.datetime = datetime.datetime.now(),
    color: Union[discord.Color, int] = MISSING,
) -> discord.Embed:
    """A method used to have a consistent color across all bot Embeds.
    
    .. note::
        
        This is also so I can change the bots color easily when needed.
    """
    if color is MISSING:
        color = discord.Color.blue()
        
    return discord.Embed(
        title=title,
        description=description,
        timestamp=timestamp,
        color=color,
        url=url
    )


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
    if TYPE_CHECKING:
        logging_webhook_url: str
        message_webhook_url: str
        
    def __init__(self, pool: asyncpg.Pool, session: aiohttp.ClientSession):
        super().__init__(
            help_command=None,
            description='The Discord bot for the FLVS Fury server.',
            intents=discord.Intents.all(),
            guild_ids=[757664675864248360]
        )
        
        self.pool: asyncpg.Pool = pool
        self.session: aiohttp.ClientSession = session
        
        self.Embed: discord.Embed = Embed
        self.debug: bool = True
        self.start_time: datetime.datetime = datetime.datetime.utcnow()
        self.mystbin: mystbin.Client = mystbin.Client(session=self.session)
        
        # Lockdown timer
        self.lockdown_timer: TimerHandler = TimerHandler(self, 'lockdowns')
        self.lockdowns: Dict[int, Dict] = {} # Only used for local lockdowns 
        self.loop.create_task(self._propagate_lockdown_cache())
        
        # Webhooks
        self.logging_webhook_url = logging_webhook
        self.message_webhook_url = message_webhook
        
        # Mutes
        self.mute_timer: TimerHandler = TimerHandler(self, 'mutes')
        
        for ext in initial_extensions:
            try:
                self.load_extension(ext)
                log.info('Loaded ext: {0}'.format(ext))
            except Exception:
                traceback.print_exc()
                
    @classmethod
    async def setup_pool(cls) -> asyncpg.Pool:
        def _encode_jsonb(value):
            return json.dumps(value)

        def _decode_jsonb(value):
            return json.loads(value)
        
        async def init(con):
            await con.set_type_codec('jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb, format='text')
                
        pool = await asyncpg.create_pool(uri, init=init)
        return pool
                    
    async def _propagate_lockdown_cache(self) -> None:
        async with self.safe_connection() as conn:
            data = await conn.fetch('SELECT * FROM lockdowns WHERE expires IS NOT NULL AND dispatched IS FALSE;')
        
        for entry in data:
            kwargs = entry['extra']['kwargs']
            channels = kwargs['channels']
            roles = kwargs['roles']
            reason = kwargs['reason']
            
            member = entry['member']
            lockdowns = self.lockdowns
            try:
                current = lockdowns[member]
                current['reason'].append(Reasons.from_string(kwargs['reason']))
                if not current['channels']:
                    current['channels'] = channels
                    current['roles'] = roles
            except KeyError:
                lockdowns[member] = {
                    'channels': channels,
                    'roles': roles,
                    'reason': [Reasons.from_string(reason)]
                }
                
    @contextlib.asynccontextmanager
    async def safe_connection(self, timeout: Optional[float] = 10):
        """|coro|
        
        Generates a safe connection used to make database calls.
        
        Parameters
        ----------
        timeout: Optional[:class:`float`]
            The timeout to use for the connection. Defaults to 10.
        """
        conn = await self.pool.acquire(timeout=timeout)
        try:
            yield conn
        finally:
            await self.pool.release(conn)
        
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
    
    async def get_logging_webhook(self) -> discord.Webhook:
        if not hasattr(self, 'logging_webhook'):
            partial = discord.Webhook.from_url(self.logging_webhook_url, session=self.session, bot_token=self.http.token)
            self.logging_webhook = await partial.fetch()
        
        return self.logging_webhook
    
    async def send_to_logging_channel(self, *args, **kwargs) -> None:
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
        None
        """
        await self.wait_until_ready()
        
        webhook = await self.get_logging_webhook()

        ping_staff = kwargs.pop('ping_staff', True)
        if ping_staff:
            if args:
                kwargs['content'] = args[0]
                
            if content := kwargs.get('content'):
                content = f'<@&867901004728762399>\n{content}'
            else:
                kwargs['content'] ='<@&867901004728762399>'
            kwargs['allowed_mentions'] = discord.AllowedMentions(roles=[discord.Object(id=867901004728762399)])
        else:
            kwargs['allowed_mentions'] = discord.AllowedMentions.none()

        return await webhook.send(
            username=self.user.display_name, 
            avatar_url=self.user.display_avatar.url,
            **kwargs
        )
    
    async def post_to_mystbin(self, content: str, syntax: str = 'python') -> mystbin.Post:
        """Post content to Mystbin and get the response back.
        
        Parameters
        ----------
        content: :class:`str`
            The content to pass along to mystbin
        syntax: :class:`str`
            The syntax to use with your upload.
            
        Returns
        -------
        :class:`mystbin.Post`
        """
        return await self.mystbin.post(content, syntax)
        
    async def on_ready(self):
        print(f"{self.user.name} has come online.")
            
    def _yield_chunks(self, value: str):
        const = 10
        
        for i in range(0, len(value), 2000):
            yield f'```py\n{value[i:i + (2000 - const)]}\n```'
            
    async def on_error(self, event, *args, **kwargs) -> None:
        """Called when the Bot runs into an error that is not handled by `on_command_error`.
        
        This will print out the error and send it to the logging channel."""
        type, value, traceback_str = sys.exc_info()
        if not type:
            raise

        trace_str = ''.join(traceback.format_exception(type, value, traceback_str))
        print(trace_str)
        for e in self._yield_chunks(trace_str):
            await self.send_to_logging_channel(e)
        
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
            
            for e in self._yield_chunks(traceback_str):
                await self.send_to_logging_channel(e)
        else:
            e.description = f'I ran into an error when doing this command!\n\n**{str(error)}**'
            return await ctx.send(embed=e)
    
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return 
        if message.channel.id == constants.MESSAGE_LOG_CHANNEL:
            return
        
        if not hasattr(self, 'message_webhook'):
            partial = discord.Webhook.from_url(self.message_webhook_url, session=self.session, bot_token=self.http.token)
            self.message_webhook = await partial.fetch()
        
        kwargs = {}
        if message.attachments:
            attachments = []
            for att in message.attachments:
                try:
                    attachments.append(await att.to_file(spoiler=att.is_spoiler()))
                except:
                    pass
            kwargs['files'] = attachments
           
        try:     
            await self.message_webhook.send(
                username=message.author.display_name,
                avatar_url=message.author.display_avatar.url,
                embeds=message.embeds,
                content=message.content,
                allowed_mentions=discord.AllowedMentions.none(),
                **kwargs
            )
        except discord.HTTPException:
            pass
            

class Security(CustomProfanity, URLExtract):
    def __init__(self):
        URLExtract.__init__(self)
        super().__init__()
        self.update()
        
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
    
    def contains_profanity(self, message: str) -> Coroutine[Any, Any, bool]:
        """Used to determine if a message has profanity.
        
        Parameters
        ----------
        message: :class:`str`
            The message to check.
        
        Returns
        -------
        :class:`bool`
        """
        return self.wrap(self.has_bad_word, message)
    
    def censor_message(self, message: str) -> Coroutine[Any, Any, str]:
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
        return self.wrap(self.censor, message)
    
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
    if TYPE_CHECKING:
        safe_connection: Callable
        lockdown_timer: TimerHandler
        lockdowns: Dict[int, Dict]
        get_guild: Callable
    
    @staticmethod
    def get_lockdown_role(guild: discord.Guild):
        return guild.get_role(constants.LOCKDOWN_ROLE)
    
    async def is_locked(self, member: Union[discord.Member, discord.User]) -> bool:
        """Determine if a member is locked.
        
        Parameters
        ----------
        member: Union[:class:`discord.Member`, :class:`discord.User`]
            The member to check.
            
        Returns
        -------
        :class:`bool`
        """
        async with self.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM lockdowns WHERE member = $1', member.id)
        
        if not data:
            return False
        return True
    
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
            return await member.send(*args, **kwargs)
        except (discord.HTTPException, discord.Forbidden):
            return None
        
    async def lockdown(
        self, 
        member: discord.Member, 
        *, 
        reason: Reasons, 
        time: Optional[datetime.datetime] = None,
        **kwargs
    ) -> bool:
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
        
        new_kwargs = {
            'reason': Reasons.type_to_string(reason),
            'channels': None,
            'roles': None,
        }
        
        channels = []
        for channel in member.guild.channels: # Remove any special team creation. EX: rocket-league-1
            overwrites = channel.overwrites
            if overwrites.get(member):
                specific = discord.utils.find(lambda e: e[0] == 'view_channel' and e[1] == True, overwrites.items())
                if specific:
                    overwrites.update(view_channel=False)
                    await channel.edit(overwrites=overwrites)
                    channels.append(channel.id)
        
        roles = [r.id for r in member.roles if r.is_assignable()]
        keep_roles = [r for r in member.roles if r not in roles]
        
        new_kwargs['channels'] = channels
        new_kwargs['roles'] = roles
        
        if member.id in self.lockdowns:
            self.lockdowns[member.id]['reason'].append(reason)
            
            # Ensure that when the timer pops the member will have their original roles and channels back
            new_kwargs['roles'] = self.lockdowns[member.id]['roles']
            new_kwargs['channels'] = self.lockdowns[member.id]['channels']
        else:
            self.lockdowns[member.id] = {
                'reason': [reason],
                'channels': channels,
                'roles': roles
            }
            
        lr = self.get_lockdown_role(member.guild)

        print([lr] + [keep_roles])
        try:
            await member.edit(roles=[lr] + [keep_roles], reason='Member is getting locked down.')
        except discord.Forbidden:
            return False
            
        async with self.safe_connection() as connection:
            if time is not None:
                await self.lockdown_timer.create_timer(
                    time,
                    member.id,
                    kwargs.get('moderator', None),
                    connection=connection,
                    **new_kwargs
                )
            else:
                await connection.execute(
                    'INSERT INTO lockdowns (event, extra, created, member, moderator) VALUES ($1, $2::jsonb, $3, $4, $5)',
                    'lockdowns', {'kwargs': new_kwargs, 'args': []}, discord.utils.utcnow(), member.id, kwargs.get('moderator', member.id)
                )
        
        embed = Embed(
            title='Oh no!',
            description=f'You have been given the **Lockdown** role in the FLVS Fury server. '
                        'This means you cannot interact with the server for now.'
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f'ID: {member.id}') 
        embed.add_field(name='Reason', value=f'Locked down for: {Reasons.type_to_string(reason)}')
        embed.add_field(name='Expires', value=f'The lockdown expires in {human_time(time) if time else "Never"}{" ({})".format(discord.utils.format_dt(time)) if time else ""}')
        
        await self.send_to(member, embed=embed)
        return True
    
    async def lockdown_for(
        self,
        seconds: int,
        member: discord.Member,
        reason: Reasons
    ) -> bool:
        # Let's convert the time first
        when = await UserFriendlyTime(converter=None, default='for lockdown').convert(context.DummyContext(), f'{seconds}s')
        return await self.lockdown(member, reason=reason, time=when.dt)
        
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
        log.info(f'Coro freedom called on {member}')
      
        if member.id not in self.lockdowns:
            return False
        
        guild = self.get_guild(constants.FURY_GUILD)
        data = self.lockdowns[member.id]
        reasons = data['reason']
        try:
            reasons.remove(reason)
        except Exception:
            pass
        
        if reasons: # The member has been locked down for more than 1 reason
            return False
        
        self.lockdowns.pop(member.id, None)
        
        channels = data['channels']
        roles = data['roles']
        
        for channel_id in channels:
            channel = guild.get_channel(channel_id)
            overwrites = channel.overwrites
            if overwrites.get(member):
                overwrites[member].update(view_channel=True)
                await channel.edit(overwrites=overwrites)
        
        clean_roles = [guild.get_role(id) for id in roles]
        await member.edit(roles=clean_roles)
        
        embed = Embed(
            title='Lockdown Ended',
            description='Your lockdown has ended! Your access to the server has been revoked. Feel free to review the rules and enjoy the server.'
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f'ID: {member.id}')
        
        await self.send_to(member, embed=embed)
        return True

         
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
    def __init__(self, pool: asyncpg.Pool, session: aiohttp.ClientSession):
        super().__init__(pool, session)
        SecurityMixin.__init__(self)