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
    Protocol,
    Union, 
    Coroutine,
    Type,
    Generic,
    Tuple,
    TypeVar,
    Callable,
    Any,
    Generator
)
from typing_extensions import ParamSpec

import aiohttp
import mystbin
import asyncpg
import googletrans

import discord
from discord.ext import commands

from utils import context, constants
from utils.errors import *
from utils import ProfanityChecker
from utils.timer import TimerManager, Timer
from utils.time import UserFriendlyTime, human_timedelta
from utils.links import LinkChecker
from config import postgresql as uri, logging_webhook, message_webhook


T = TypeVar('T')
P = ParamSpec('P')
FuryT = TypeVar('FuryT', bound='FuryBot')

__all__ = (
    'DiscordBot',
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

def _yield_chunks(value: str):
    const = 2000 - 10 # The legnth of 2000 (total content legnth) - "```py\n```"
    
    for i in range(0, len(value), const):
        yield f'```py\n{value[i:i + const]}\n```'


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

class _Chunkable(Protocol):
    def __len__(self) -> int:
        ...
        
    def __getitem__(self, __k) -> Any:
        ...
    
    

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


class DiscordBot(commands.Bot):
    """The base container for FURY Bot.
    
    Will contain all discord.py related activities and methods.
    
    Attributes
    ----------
    pool: :class:`asyncpg.Pool`
        The connection pool for the bot to use.
    session: :class:`aiohttp.ClientSession`
        The session for the bot to use.
    Embed: Callable[..., :class:`discord.Embed`]
        An embed callable to use. This gives you the bots embed to
        use across all commands.
    debug: :class:`bool`
        Whether or not the bot is in debug mode.
    spam_control: :class:`commands.CooldownMapping`
        A spam control mapping to use for members who try
        and spam messages.
    logging_webhook_url: :class:`str`
        The logging webhook url to use for the bot.
    message_webhook_url: :class:`str`
        The message webhook url to use for the bot.
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
            owner_ids=[757663899532132418, 146348630926819328],
            *args,
            **kwargs
        ) 
        
        self.Embed: Callable[..., discord.Embed] = Embed
        self.debug: bool = True
        
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
        """|coro|
        
        Used to get context of a :class:`discord.Message`.
        
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
        
        Used to get the logging webhook for Fury Bot. This is the webhook that
        is used to log anything the moderation needs to know about.
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
        *args: Tuple[Any]
            The args to send along to the channel
        **kwargs: Dict[Any, Any]
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
        :class:`discord.WebhookMessage`
            The message that was sent.
        """
        await self.wait_until_ready()
        if args:
            kwargs['content'] = args[0]
        
        ping_staff = kwargs.pop('ping_staff', True)
        
        if ping_staff:
            mentions = discord.AllowedMentions(roles=[discord.Object(id=constants.LOCKDOWN_NOTIFICATIONS_ROLE)])
            
            if (content := kwargs.get('content')):
                content = f'<@&{constants.LOCKDOWN_NOTIFICATIONS_ROLE}>\n{content}'
            else:
                content = f'<@&{constants.LOCKDOWN_NOTIFICATIONS_ROLE}>'
            
            kwargs['content'] = content
        else:
            mentions = discord.AllowedMentions.none()
        
        kwargs['allowed_mentions'] = mentions

        webhook = await self.get_logging_webhook()
        return await webhook.send(
            username=self.user.display_name, 
            avatar_url=self.user.display_avatar.url,
            **kwargs
        )
        
    async def on_ready(self):
        """|coro|
        
        An event that's called when the bot's internal state reaches ready. At this point,
        cahce has been fully populated and the bot is ready to be used.
        """
        log.info(f"{self.user.name} has come online.")
        log.info(discord.utils.oauth_url(
            self.application_id, # type: ignore
            permissions=discord.Permissions(8), 
        ))
            
    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        """Called when the Bot runs into an error that is not handled by `on_command_error`.
        
        This will log error and send it to the logging channel.
        
        Parameters
        ----------
        event_method: :class:`str`
            The name of the method that created the error.
        *args: Any
            The arguments that were passed to the method.
        **kwargs: Any
            The keyword arguments that were passed to the method.
        """
        type, value, traceback_str = sys.exc_info()
        if not type:
            raise

        trace_str = ''.join(traceback.format_exception(type, value, traceback_str))
        log.exception(f'Exception in {event_method}', exc_info=value)
        
        for e in _yield_chunks(trace_str):
            await self.send_to_logging_channel(e)


class FuryBot(DiscordBot, TimerManager):
    """
    The main implementation of Fury Bot. This combines
    both the Discord Bot and the Timer Manager into one, and adds
    methods to the bot that are used to manage lockdowns, profanity,
    and link checking.
    
    Attributes
    ----------
    profanity: :class:`ProfanityChecker`
        The profanity manager for the bot.
    links: :class:`LinkChecker`
        The link checker for the bot.
    executor: :class:`concurrent.futures.ThreadPoolExecutor`
        The executor used to run tasks in the background.
    mystbin: :class:`Mystbin`   
        The mystbin manager for the bot.
    start_time: :class:`datetime.datetime`
        The time the bot started, in utc.
    """
    def __init__(self, *, pool: asyncpg.Pool, session: aiohttp.ClientSession, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(pool=pool, session=session, loop=loop)
        self.profanity = ProfanityChecker(wrap=self.wrap, safe_connection=self.safe_connection)
        self.links: LinkChecker = LinkChecker(wrap=self.wrap, safe_connection=self.safe_connection, extract_email=True)
        
        self.executor = ThreadPoolExecutor(max_workers=15)
        self.mystbin: mystbin.Client = mystbin.Client(session=self.session) # type: ignore
        self.start_time: datetime.datetime = datetime.datetime.utcnow()
        self.translator = googletrans.Translator()
    
        self._have_data = asyncio.Event()
        self._current_timer = None
        
    @staticmethod
    def chunker(iterable: Union[str, _Chunkable], /, *, size: int = 2000) -> Generator[Union[str, _Chunkable], None, None]:
        """
        A generator used to chunk a string or iterable.
        
        Parameters
        ----------
        iterable: Union[:class:`str`, :class:`_Chunkable`]
            The iterable to chunk.
        size: :class:`int`
            The size of each chunk.
        
        Yields
        -------
        Union[:class:`str`, :class:`_Chunkable`]
            The chunked iterable.
        """
        for i in range(0, len(iterable), size):
            yield iterable[i:i + size]
        
    @discord.utils.cached_property
    def uptime_timestamp(self) -> str:
        """:class:`str`: The uptime of the bot in a human-readable Discord timestamp format.
        
        Raises
        ------
        AttributeError
            The bot has not hit on-ready yet.
        """
        if not self.is_ready():
            raise AttributeError('The bot has not hit on-ready yet.')
        
        return discord.utils.format_dt(self.start_time)
    
    @discord.utils.cached_property
    def fury_guild(self) -> discord.Guild:
        """:class:`discord.Guild`: The FLVS Fury guild."""
        guild = self.get_guild(constants.FURY_GUILD)
        if not guild:
            raise ValueError(f'Could not find guild {constants.FURY_GUILD}')

        return guild
    
    def get_lockdown_role(self) -> discord.Role:
        """:class:`discord.Role`: Get the lockdown role for the guild."""
        role = self.fury_guild.get_role(constants.LOCKDOWN_ROLE)
        if not role:
            raise RuntimeError('Get lockdown role returned None')

        return role
    
    async def setup_hook(self) -> None:
        """|coro|
        
        Called before the bot is ready to setup all extensions.
        """
        self.loop.create_task(self.dispatch_timers())
        await super().setup_hook()
        
    async def wrap(self, method: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """|coro|
        
        A utility method used to wrap a blocking call in a `run_in_executor` to not block the bot.
        
        Parameters
        ----------
        method: Callable[P, T]
            The method to wrap.
        *args: P.args
            The arguments to pass to the method.
        **kwargs: P.kwargs
            The keyword arguments to pass to the method.
        
        Returns
        -------
        T
            The result of the method.
        """
        wrapped = functools.partial(method, *args, **kwargs)
        return await self.loop.run_in_executor(self.executor, wrapped)

    async def censor(self, text: str) -> str:
        """|coro|
        
        Censor a text string using the profanity manager.
        
        Parameters
        ----------
        text: :class:`str`
            The text to censor.
        
        Returns
        -------
        :class:`str`
            The censored text.
        """
        return await self.profanity.censor(text)
    
    async def contains_profanity(self, text: str) -> bool:
        """|coro|
        
        Used to determine if a message has profanity.
        
        Parameters
        ----------
        text: :class:`str`
            The text to check.
        
        Returns
        -------
        :class:`bool`
            Whether or not the text contains profanity.
        """
        return await self.profanity.censor(text, fast=True) != text
    
    async def get_links(self, text: str) -> List[str]:
        """|coro|
        
        Extract links from a a text string.
        
        Parameters
        ----------
        text: :class:`str`
            The text to extract URL's from.
        
        Returns
        -------
        List[:class:`str`]
            The list of url's extracted from the text.
        """
        return await self.links.get_links(text)
    
    async def contains_links(self, text: str) -> bool:
        """|coro|
        
        Determine if a text contains links.
            
        Parameters
        ----------
        text: :class:`str`
            The text to determine.
            
        Returns
        -------
        :class:`bool
            Whether or not the text contains links.
        """
        return await self.links.contains_links(text)
    
    async def is_valid_link(self, link: str) -> bool:
        """|coro|
        
        A method used to determine if a link is valid or not. A valid
        link is one that has been authorized for use by the moderation team.
        
        Parameters
        ----------
        link: :class:`str`
            The link to check.
        
        Returns
        -------
        :class:`bool`
            Whether or not the link is valid.
        """
        return await self.links.is_valid_link(link)
    
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
        return await self.mystbin.post(content, syntax) # type: ignore # This is not of concern to us.
    
    async def translate(self, text: str) -> str:
        """|coro|
        
        Used to translate text from one language to another.
        
        Parameters
        ----------
        text: :class:`str`
            The text to translate.
            
        Returns
        -------
        :class:`str`
            The translated text.
        """
        return await self.wrap(self.translator.translate(text))
        
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
    
    async def send_to(self, member: discord.abc.Messageable, *args, **kwargs) -> Optional[discord.Message]:
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
        
        lr = self.get_lockdown_role()
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
        
        self.dispatch('lockdowns_timer_complete', timer)
        return True