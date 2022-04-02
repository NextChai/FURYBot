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
import time
import logging
import traceback
import functools
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import (
    TYPE_CHECKING,
    Awaitable,
    List,
    Dict, 
    Optional, 
    Union, 
    Coroutine,
    Type,
    Generic,
    Tuple,
    TypeVar,
    Callable,
    Any
)
from typing_extensions import ParamSpec

import aiohttp
import mystbin
import asyncpg

import discord
from discord.ext import commands

from urlextract import URLExtract

from utils import context, checks, constants
from utils.errors import *
from utils import CustomProfanity
from utils.timer import TimerManager, Timer
from utils.time import UserFriendlyTime, human_timedelta
from config import postgresql as uri, logging_webhook, message_webhook


T = TypeVar('T')
P = ParamSpec('P')
FuryT = TypeVar('FuryT', bound='FuryBot')

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
    # Utilities
    'utils.error_handler',
    'utils.help',
    'utils.jishaku',
    
    'cogs.commands',
    'cogs.owner',
    'cogs.moderation',
    #'cogs.safety',
    'cogs.teams',
)


@discord.utils.copy_doc(discord.Embed)
def Embed(
    *,
    title: str = MISSING,
    description: str = MISSING,
    url: str = MISSING,
    timestamp: datetime.datetime = datetime.datetime.now(),
    color: Union[discord.Color, int] = MISSING,
    author: Union[discord.User, discord.Member] = MISSING,
    cls: Optional[Type[discord.Embed]] = None
) -> discord.Embed:
    """A method used to have a consistent color across all bot Embeds.
    
    Parameters
    ----------
    title: :class:`str`
        The title of the embed.
    description: :class:`str`
        The description of the embed.
    url: :class:`str`
        The url of the embed.
    timestamp: :class:`datetime.datetime`
        The timestamp of the embed. Defaults to the current time.
    color: :class:`discord.Color`
        The color of the embed.
    author: Union[:class:`discord.User`, :class:`discord.Member`]
        The author of the embed.
    cls: Optional[Type[:class:`discord.Embed`]]
        The embed class to use. Defaults to :class:`discord.Embed`.
    """
    new_cls = cls or discord.Embed
    
    kwargs: Dict[str, Union[str, datetime.datetime, discord.Color]] = {
        'timestamp': timestamp
    }
    
    if color is MISSING:
        kwargs['color'] = discord.Color.blue()
    if title is not MISSING:
        kwargs['title'] = title
    if description is not MISSING:
        kwargs['description'] = description
    if url is not MISSING:
        kwargs['url'] = url
    
    new = new_cls(**kwargs)

    if author is not MISSING:
        new.set_author(name=str(author), icon_url=author.display_avatar.url)
        new.set_footer(text=f'ID: {author.id}')
        
    return new

def _wrap_extension(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[Optional[T]]]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
        fmt_args = 'on ext "{}"{}'.format(args[1], f' with kwargs {kwargs}' if kwargs else '')
        start = time.perf_counter()
        
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            log.warning(f'Failed to load extension in {time.perf_counter() - start:.2f} seconds {fmt_args}', exc_info=exc)
            return
        
        fmt = f'{func.__name__} took {time.perf_counter() - start:.2f} seconds {fmt_args}'
        log.info(fmt)
        
        return result
    
    return wrapped


class DbContextManager(Generic[FuryT]):
    """A simple context manager used to manage database connections.
    
    Please note this was created instead of using `contextlib.asynccontextmanager` because
    I plan to add additional functionality to this class in the future.
    
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    timeout: :class:`float`
        The timeout for acquiring a connection.
    """
    
    __slots__: Tuple[str, ...] = (
        'bot',
        'timeout',
        '_pool',
        '_conn',
        '_tr'
    )
    
    def __init__(self, bot: FuryT, *, timeout: float = 10.0) -> None:
        self.bot: FuryT = bot
        self.timeout: float = timeout
        self._pool: asyncpg.Pool = bot.pool
        self._conn: Optional[asyncpg.Connection] = None
        self._tr: Optional[asyncpg.Transaction] = None
        
    async def acquire(self) -> asyncpg.Connection:
        return await self.__aenter__()
    
    async def release(self) -> None:
        return await self.__aexit__(None, None, None)
    
    async def __aenter__(self) -> asyncpg.Connection:
        self._conn = conn = await self._pool.acquire(timeout=self.timeout)
        self._tr = conn.transaction()
        await self._tr.start()
        return conn
    
    async def __aexit__(self, exc_type, exc, tb):
        if exc and self._tr:
            await self._tr.rollback()
            
        elif not exc and self._tr:
            await self._tr.commit()
            
        if self._conn:
            await self._pool.release(self._conn)


class DiscordBot(commands.Bot, TimerManager):
    """The base container for FURY Bot.
    
    Will contain all discord.py related activities and methods.
    
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
        
        # This is mainly to ignore NoneType errors.
        # This won't be used unless the bot is ready and this
        # is not None.
        user: discord.ClientUser
        
    def __init__(self, pool: asyncpg.Pool, session: aiohttp.ClientSession, *args, **kwargs):
        self.pool: asyncpg.Pool = pool
        self.session: aiohttp.ClientSession = session
        
        super().__init__(
            help_command=commands.MinimalHelpCommand(),
            description='The Discord bot for the FLVS Fury server.',
            intents=discord.Intents.all(),
            command_prefix={'fury.', 'f.'},
            strip_after_prefix=True,
            hartbeat_timeout=180,
            case_insensitive=True,
            owner_ids=[757663899532132418, 146348630926819328] 
        ) 
        TimerManager.__init__(self, self) # type: ignore
    
        self.Embed: Callable[..., discord.Embed] = Embed
        self.debug: bool = True
        self.mystbin: mystbin.Client = mystbin.Client(session=self.session) # type: ignore
        
        # TODO: Implement me
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 12.0, commands.BucketType.user)
        
        # Webhooks
        self.logging_webhook_url = logging_webhook
        self.message_webhook_url = message_webhook
        self._webhook_lock: asyncio.Lock = asyncio.Lock()
                
    @classmethod
    async def setup_pool(cls) -> asyncpg.Pool:
        """:meth: `asyncpg.create_pool` with some extra functionality.

        Parameters
        ----------
        uri: :class:`str`
            The Postgres connection URI.
        **kwargs:
            Extra keyword arguments to pass to :meth:`asyncpg.create_pool`.
        """
        def _encode_jsonb(value):
            return discord.utils._to_json(value)

        def _decode_jsonb(value):
            return discord.utils._from_json(value)
        
        async def init(con):
            await con.set_type_codec('jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb, format='text')
                
        pool = await asyncpg.create_pool(uri, init=init)
        return pool
    
    @_wrap_extension
    @discord.utils.copy_doc(commands.Bot.load_extension)
    def load_extension(self, name: str, *, package: Optional[str] = None) -> Coroutine[Any, Any, None]:
        return super().load_extension(name, package=package)
    
    @_wrap_extension
    @discord.utils.copy_doc(commands.Bot.unload_extension)
    def unload_extension(self, name: str, *, package: Optional[str] = None) -> Coroutine[Any, Any, None]:
        return super().unload_extension(name, package=package)
    
    @_wrap_extension
    @discord.utils.copy_doc(commands.Bot.reload_extension)
    def reload_extension(self, name: str, *, package: Optional[str] = None) -> Coroutine[Any, Any, None]:
        return super().reload_extension(name, package=package)
    
    async def load_extensions(self, /, *, force_task: bool = True) -> List[Optional[asyncio.Task[None]]]:
        """Loads the bot's extensions.
        
        Parameters
        ----------
        force_task: :class:`bool`
            Whether or not to force the task to run :meth:`Scott.load_extensions`. This is for any
            modules that wish to wait for an event to be fired before loading.
        """
        if force_task:
            return [self.loop.create_task(self.load_extension(ext)) for ext in initial_extensions] # type: ignore
        
        return [await self.load_extension(ext) for ext in initial_extensions] # type: ignore
    
    async def setup_hook(self) -> None:
        """|coro|
        
        Called before the bot is ready to setup all extensions.
        """
        self._task: Optional[asyncio.Task] = self.loop.create_task(self.dispatch_timers())
        
        await self.load_clean_words() # type: ignore
        await self.load_dirty_words() # type: ignore
        
        await self.load_extensions()
            
    def safe_connection(self, timeout: float = 10) -> DbContextManager:
        """|coro|
        
        Generates a safe connection used to make database calls.
        
        Parameters
        ----------
        timeout: Optional[:class:`float`]
            The timeout to use for the connection. Defaults to 10.
        """
        return DbContextManager(self, timeout=timeout) # type: ignore
        
    async def get_context(self, message: discord.Message, *, cls: Type[context.Context] = context.Context) -> Any:
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
        return await super().get_context(message, cls=cls)
    
    async def get_logging_webhook(self) -> discord.Webhook:
        """|coro|
        
        Used to get the logging webhook for fury bot. This is the webhook that will be used to log events
        to the logging channel.
        """
        if not (webhook := getattr(self, 'logging_webhook', None)):
            partial = discord.Webhook.from_url(self.logging_webhook_url, session=self.session, bot_token=self.http.token)
            self.logging_webhook = webhook = await partial.fetch()
        
        return webhook
    
    async def send_to_logging_channel(self, *args, **kwargs) -> discord.WebhookMessage:
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

        # NOTE: Update this later
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
    
    async def post_to_mystbin(self, content: str, syntax: str = 'python'):
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
        return await self.mystbin.post(content, syntax) # type: ignore
        
    async def on_ready(self):
        log.info(f"{self.user.name} has come online.")
        log.info(discord.utils.oauth_url(
            self.application_id, # type: ignore
            permissions=discord.Permissions(8), 
            scopes=('bot', 'applications.commands')
        ))
            
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
    
    async def on_message(self, message: discord.Message) -> None:
        await self.process_commands(message)
        
        if any((
            message.channel.id == constants.MESSAGE_LOG_CHANNEL,
            message.author.bot,
            not message.guild,
        )):
            return
        
        # Make the type checker happy here:
        channel = message.channel
        if isinstance(channel, (discord.DMChannel, discord.PartialMessageable, discord.GroupChannel)):
            return
        
        if not hasattr(self, 'message_webhook'):
            partial = discord.Webhook.from_url(self.message_webhook_url, session=self.session, bot_token=self.http.token)
            self.message_webhook = await partial.fetch()
        
        attachments = []
        if message.attachments:
            for att in message.attachments:
                try:
                    attachments.append(await att.to_file(spoiler=att.is_spoiler()))
                except:
                    pass
        
        embed = discord.Embed(description=message.content)
        embed.add_field(name='Channel', value=channel.mention)
        async with self._webhook_lock:
            try:     
                await self.message_webhook.send(
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    allowed_mentions=discord.AllowedMentions.none(),
                    files=attachments,
                    embed=embed
                )
            except discord.HTTPException:
                pass
            

class Security(CustomProfanity, URLExtract):
    def __init__(self):
        URLExtract.__init__(self)
        super().__init__()
        self.update()
        self.executor = ThreadPoolExecutor(max_workers=15)
        
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
        return await self.loop.run_in_executor(self.executor, wrapped)
    
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
        return (await self.get_links(message)) != []
    
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
        return True if check else False
        
        
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
        get_guild: Callable
        get_cog: Callable[[str], Optional[commands.Cog]]
        wait_until_ready: Callable
        create_timer: Callable
    
    @staticmethod
    def get_lockdown_role(guild: discord.Guild) -> discord.Role:
        role = guild.get_role(constants.LOCKDOWN_ROLE)
        if not role:
            raise RuntimeError('Get lockdown role returned None')

        return role
    
    async def is_locked(
        self, 
        member: Union[discord.Member, discord.User], 
        *, 
        return_record: bool = False, 
        connection: Optional[asyncpg.Connection] = None
    ) -> bool:
        """Determine if a member is locked.
        
        Parameters
        ----------
        member: Union[:class:`discord.Member`, :class:`discord.User`]
            The member to check.
        return_record: Optional[:class:`bool`]
            Denotes if the record should be returned.
        connection: Optional[:class:`asyncpg.Connection`]
            The connection to use, if any.

        Returns
        -------
        :class:`bool`
        """
        query = 'SELECT * FROM timers WHERE extra#>\'{kwargs, member}\' = $1 AND extra#>\'{kwargs, type}\' = $2 AND dispatched = $3'
        if not connection:
            async with self.safe_connection() as conn:
                data = await conn.fetchrow(query, member.id, 'lockdowns', False)
        else:
            data = await connection.fetchrow(query, member.id, 'lockdowns', False)
        
        if return_record: 
            return data
        
        return False if not data else True
    
    async def send_to(self, member: Union[discord.Member, discord.User], *args, **kwargs) -> Optional[discord.Message]:
        """Neatly sends a message to a member. Any exceptions thrown will be quietly handled.
        
        Parameters
        ----------
        member: Union[:class:`discord.Member`, :class:`discord.User`]
            The member or user to send to.
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
        reason: Optional[str] = None, 
        time: Optional[datetime.datetime] = None,
        **kwargs
    ) -> bool:
        """Adds a user to Lockdown.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to Lockdown.
        reason: Optional[:class:`str`]
            The reason for locking down the member.
        raise_for_exception: Optional[:class:`bool`]
            Whether or not to raise an exception if the member is already locked.
            
        Returns
        -------
        :class:`bool`
            Tells you if the member's Lockdown role is new. 
                - True = lockdown is new
                - False = the user's lockdown has been extended for another reason.
                
        Raises
        ------
        MemberAlreadyLocked
            The member is already locked.
        """
        log.info('Coro lockdown was called on %s for reason %s', member, reason)
        
        raise_for_exception = kwargs.pop('raise_for_exception', True)
        
        if await self.is_locked(member):
            if not raise_for_exception:
                return False
            
            raise MemberAlreadyLocked(f'Member {member} is already locked.')
        
        channels = []
        for channel in member.guild.channels: # Remove any special team creation. EX: rocket-league-1
            overwrites = channel.overwrites
            if overwrites.get(member):
                specific = discord.utils.find(lambda e: e[0] == 'view_channel' and e[1] == True, overwrites.items())
                if specific:
                    overwrites[member].update(view_channel=False) 
                    await channel.edit(overwrites=overwrites) # type: ignore
                    channels.append(channel.id)
                    
        kwargs['channels'] = channels
        kwargs['roles'] = [r.id for r in member.roles if r.is_assignable()]
        kwargs['reason'] = reason
        
        lr = self.get_lockdown_role(member.guild)
        roles = [lr]
        roles.extend([r for r in member.roles if not r.is_assignable()]) # The role(s) a bot can not change.
        
        try:
            await member.edit(roles=roles, reason='Member is getting locked down.')
        except discord.Forbidden:
            return False
            
        await self.create_timer(
            time,
            'lockdowns',
            precise=False,
            member=member.id,
            type='lockdowns',
            **kwargs
        )
        
        embed = Embed(
            title='Oh no!',
            description=f'You have been given the **Lockdown** role in the FLVS Fury server. '
                        'This means you cannot interact with the server for now.',
            author=member
        )
        embed.add_field(name='Reason', value=f'Locked down for reason: {reason}')
        embed.add_field(name='Expires', value=f'The lockdown expires in {human_timedelta(time) if time else "Never"}{" ({})".format(discord.utils.format_dt(time)) if time else ""}')
        
        await self.send_to(member, embed=embed)
        return True
    
    async def lockdown_for(
        self,
        seconds: int,
        member: discord.Member,
        *,
        reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        """|coro|
        
        Used to lockdown a member for a specific amount of time.
        
        Parameters
        ----------
        seconds: :class:`int`
            The total time, in seconds, to lockdown the member.
        member: :class:`discord.Member`
            The member to Lockdown.
        reason: Optional[:class:`str`]
            The reason for locking down the member.
        raise_for_exception: Optional[:class:`bool`]
            Whether or not to raise an exception if the member is already locked.
            
        Returns
        -------
        :class:`bool`
            Tells you if the member's Lockdown role is new. 
                - True = lockdown is new
                - False = the user's lockdown has been extended for another reason.
                
        Raises
        ------
        MemberAlreadyLocked
            The member is already locked.
        
        """
        # Let's convert the time first
        when = await UserFriendlyTime(converter=None, default='for lockdown').convert(context.DummyContext(), f'{seconds}s') # type: ignore
        return await self.lockdown(member, reason=reason, time=when.dt, **kwargs)
        
    async def freedom(self, member: discord.Member, *, raise_for_exception: bool = True) -> bool:
        """|coro|
        
        Called to prematurely remove the lockdown timer, this will override the existing timer.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to free from lockdown.
        raise_for_exception: Optional[:class:`bool`]
            Whether or not to raise an exception if the member is not locked.
            
        Returns
        -------
        :class:`bool`
            Whether or not the unlock was successful.
            
        Raises
        ------
        MemberNotLocked
            The Member was not locked.
        """
        log.info(f'Coro freedom called on {member}')
        
        # Called to prematurely remove the lockdown timer.
        async with self.safe_connection() as conn:
            if not (data := await self.is_locked(member, return_record=True, connection=conn)):
                if not raise_for_exception:
                    return False
                
                raise MemberNotLocked(f'Member {member} is not locked.')
            
            timer = Timer(record=data)
            await conn.execute('UPDATE timers SET dispatched = $1 WHERE id = $2', True, timer.id)
            
        timer.member = member
        
        await self.on_lockdowns_timer_complete(timer)
        return True
    
    async def on_lockdowns_timer_complete(self, timer: Timer) -> None:
        await self.wait_until_ready()
        
        guild = self.get_guild(constants.FURY_GUILD)
        
        if not (member := getattr(timer, 'member', None)):
            member = guild.get_member(timer.kwargs['member']) or await guild.fetch_member(timer.kwargs['member'])
        
        log.info(f'On lockdowns timer complete for member {member}')
        
        # Restore roles here
        channels = timer.kwargs['channels']
        roles = timer.kwargs['roles']
        
        for channel in channels:
            channel = guild.get_channel(channel)
            if not channel:
                continue
            
            overwrites = channel.overwrites
            if overwrites.get(member):
                overwrites[member].update(view_channel=True)
                await channel.edit(overwrites=overwrites)
        
        keep_roles = member.roles
        keep_roles_fmt = [kr.id for kr in keep_roles]
        try:
            keep_roles.remove(self.get_lockdown_role(guild))
        except:
            pass
        
        keep_roles.extend([discord.Object(id=r) for r in roles if r not in keep_roles_fmt])
        await member.edit(roles=keep_roles)
        
        embed = Embed(
            title='Lockdown Ended',
            description='Your lockdown has ended! You access tot he server has been restored. Feel free to review the rules and enjoy the server.'
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f'ID: {member.id}')
        embed.add_field(name='Locked Since', value=f'{human_timedelta(timer.created_at)} ({discord.utils.format_dt(timer.created_at)}).')
        await self.send_to(member, embed=embed)
        
         
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
    __is_fury_bot__ = True
    
    def __init__(self, pool: asyncpg.Pool, session: aiohttp.ClientSession, loop: asyncio.AbstractEventLoop):
        super().__init__(pool, session, loop)
        SecurityMixin.__init__(self)