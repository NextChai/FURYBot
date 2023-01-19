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

import asyncio
import functools
import logging
import os
import time
from concurrent import futures
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Literal,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    cast,
)

import asyncpg
import discord
from discord.ext import commands
from typing_extensions import Concatenate, Self

from cogs.images import ApproveOrDenyImage, ImageRequest
from cogs.teams import Team

from cogs.teams.practices import Practice
from cogs.teams.scrim import Scrim, ScrimStatus
from utils import RUNNING_DEVELOPMENT, ErrorHandler, LinkFilter, TimerManager

if TYPE_CHECKING:
    import datetime

    import aiohttp

T = TypeVar('T')
P = ParamSpec('P')
PoolType: TypeAlias = 'asyncpg.Pool[asyncpg.Record]'
ConnectionType: TypeAlias = 'asyncpg.Connection[asyncpg.Record]'
DecoFunc: TypeAlias = Callable[Concatenate['FuryBot', P], Coroutine[T, Any, Any]]

_log = logging.getLogger(__name__)

initial_extensions: Tuple[str, ...]
if RUNNING_DEVELOPMENT:
    initial_extensions = tuple(v for k, v in os.environ.items() if k.startswith('FURY_EXTENSION'))
else:
    initial_extensions = (
        'jishaku',
        'cogs.events.infractions',
        'cogs.events.notifier',
        'cogs.infractions',
        'utils.error_handler',
        'cogs.owner',
        'cogs.events.tracking',
        'cogs.teams',
        # 'cogs.teams.practices',
        'cogs.images',
        'cogs.moderation',
    )


def wrap_extension(coro: DecoFunc[P, T]) -> DecoFunc[P, T]:
    """A method to wrap an extension coroutine in the Bot class. This will handle all
    logging and error handling.

    Parameters
    ----------
    coro: DecoFunc[P, T]
        The coroutine to wrap.

    Returns
    -------
    DecoFunc[P, T]
        A wrapped function that logs and handles errors.
    """

    async def wrapped(self: FuryBot, *args: P.args, **kwargs: P.kwargs) -> T:
        ext_name, *_ = args

        start = time.time()
        try:
            result = await coro(self, *args, **kwargs)
        except commands.ExtensionFailed as exc:
            raise exc.original from exc
        except Exception as exc:
            raise exc from None

        _log.info(f'Loaded the "{ext_name}" extension in {time.time() - start:.2f} seconds')
        return result

    return wrapped


class DbContextManager:
    """A simple context manager used to manage database Connectionections.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    timeout: :class:`float`
        The timeout for acquiring a Connectionection.
    """

    __slots__: Tuple[str, ...] = ('bot', 'timeout', '_pool', '_Connection', '_tr', '_connection')

    def __init__(self, bot: FuryBot, *, timeout: Optional[float] = 10.0) -> None:
        self.bot: FuryBot = bot
        self.timeout: Optional[float] = timeout
        self._pool: PoolType = bot.pool
        self._connection: Optional[ConnectionType] = None
        self._tr: Optional[Any] = None

    async def acquire(self) -> ConnectionType:
        return await self.__aenter__()

    async def release(self) -> None:
        await self.__aexit__(None, None, None)

    async def __aenter__(self) -> ConnectionType:
        self._connection = connection = await self._pool.acquire(timeout=self.timeout)  # type: ignore
        self._tr = tr = connection.transaction()
        await tr.start()
        return connection  # type: ignore

    async def __aexit__(
        self, exc_type: Optional[Type[Exception]], exc: Optional[Exception], tb: Optional[Type[Exception]]
    ) -> None:
        if exc and self._tr:
            await self._tr.rollback()

        elif not exc and self._tr:
            await self._tr.commit()

        if self._connection:
            await self._pool.release(self._connection)  # type: ignore


class FuryBot(commands.Bot):
    """The main fury bot instance. This bot subclass contains many useful utiities
    shared between all extensions / cogs.

    Parameters
    ----------
    loop: :class:`asyncio.AbstractEventLoop`
        The current running event loop.
    session: :class:`aiohttp.ClientSession`
        A client session to use for generic requests.
    pool: :class:`asyncpg.Pool`
        A database pool connection to use for requests.
    """

    if TYPE_CHECKING:
        user: discord.ClientUser  # This isn't accessed before the client has been logged in so it's OK to overwrite it.
        error_handler: ErrorHandler

    def __init__(self, *, loop: asyncio.AbstractEventLoop, session: aiohttp.ClientSession, pool: PoolType) -> None:
        self.loop: asyncio.AbstractEventLoop = loop
        self.session: aiohttp.ClientSession = session
        self.pool: PoolType = pool
        self.thread_pool: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(max_workers=20)

        _start_timer_manager = os.environ.get('FURY_START_TIMER_MANAGER')
        if _start_timer_manager is None or _start_timer_manager.lower() in ('true', '1'):
            self.timer_manager: TimerManager = TimerManager(bot=self)

        self.link_filter: LinkFilter = LinkFilter(self)

        self.team_cache: Dict[int, Team] = {}
        self.team_scrim_cache: Dict[int, Scrim] = {}
        self.team_practice_cache: Dict[int, Practice] = {}

        super().__init__(
            command_prefix=commands.when_mentioned_or('fury.'),
            help_command=None,
            description='A helpful moderation tool',
            intents=discord.Intents.all(),
            strip_after_prefix=True,
            allowed_mentions=discord.AllowedMentions.none(),
            max_messages=5000,
        )

    @classmethod
    async def setup_pool(cls: Type[Self], *, uri: str, **kwargs: Any) -> PoolType:
        """:meth: `asyncpg.create_pool` with some extra functionality.

        Parameters
        ----------
        uri: :class:`str`
            The Postgres Connectionection URI.
        **kwargs:
            Extra keyword arguments to pass to :meth:`asyncpg.create_pool`.
        """

        def _encode_jsonb(value: Dict[Any, Any]) -> str:
            return discord.utils._to_json(value)

        def _decode_jsonb(value: str) -> Dict[Any, Any]:
            return discord.utils._from_json(value)

        old_init = kwargs.pop('init', None)

        async def init(con: asyncpg.Connection[asyncpg.Record]) -> None:
            await con.set_type_codec(
                'jsonb', schema='pg_catalog', encoder=_encode_jsonb, decoder=_decode_jsonb, format='text'
            )
            if old_init is not None:
                await old_init(con)

        pool = await asyncpg.create_pool(uri, init=init, **kwargs)
        assert pool

        return pool

    @staticmethod
    def Embed(
        *,
        colour: Optional[Union[int, discord.Colour]] = None,
        color: Optional[Union[int, discord.Colour]] = None,
        title: Optional[Any] = None,
        type: Literal['rich', 'image', 'video', 'gifv', 'article', 'link'] = 'rich',
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        timestamp: Optional[datetime.datetime] = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
    ) -> discord.Embed:
        """Get an instance of the bot's global :class:`discord.Embed` with the default
        bot's color, "Craig yellow".

        The parameters are the same as :class:`discord.Embed` except for one additional one.

        Parameters
        ----------
        author: Optional[Union[:class:`discord.User`, :class:`discord.Member`]]
            An optional author of this embed. When passed, will call :meth:`Embed.set_author` and set
            the author's name nad icon url.

        Returns
        -------
        :class:`discord.Embed`
        """
        embed = discord.Embed(
            title=title, description=description, url=url, color=color, colour=colour, type=type, timestamp=timestamp
        )

        if author:
            embed.set_author(name=author.name, icon_url=author.display_avatar.url)

        return embed

    async def _load_image_request(self, data: asyncpg.Record) -> None:
        await self.wait_until_ready()

        guild = self.get_guild(data['guild_id'])
        if not guild:
            return

        channel = cast(
            Optional[Union[discord.TextChannel, discord.VoiceChannel, discord.Thread]], guild.get_channel(data['channel_id'])
        )
        if not channel:
            return

        request = ImageRequest(
            requester=await guild.fetch_member(data['requester_id']),
            attachment=discord.Attachment(data=data['attachment'], state=self._connection),
            channel=channel,
            message=data['message'],
            id=data['id'],
        )

        view = ApproveOrDenyImage(self, request)
        self.add_view(view, message_id=data['message_id'])

    # Hooks
    async def setup_hook(self) -> None:
        for extension in initial_extensions:
            await self.load_extension(extension)

        async with self.safe_connection() as connection:
            team_data = await connection.fetch('SELECT * FROM teams.settings')
            team_members_data = await connection.fetch('SELECT * FROM teams.members')

            scrim_records = await connection.fetch('SELECT * FROM teams.scrims')

            image_requests = await connection.fetch('SELECT * FROM image_requests')

            practice_data = await connection.fetch("SELECT * FROM teams.practice")
            practice_member_data = await connection.fetch("SELECT * FROM teams.practice_member")
            practice_member_history_data = await connection.fetch("SELECT * FROM teams.practice_member_history")

        team_member_mapping: Dict[int, List[Dict[Any, Any]]] = {}
        for entry in team_members_data:
            team_member_mapping.setdefault(entry['team_id'], []).append(dict(entry))

        for row in team_data:
            members = team_member_mapping.get(row['id'], [])
            team = await Team.from_record(dict(row), members, bot=self)
            self.team_cache[team.id] = team

        for entry in scrim_records:
            data = dict(entry)
            data['status'] = ScrimStatus(data['status'])

            scrim = Scrim(self, **data)
            scrim.load_persistent_views()
            self.team_scrim_cache[scrim.id] = scrim

        for request in image_requests:
            self.create_task(self._load_image_request(request))

        # mapping of practice id to member id to practice member data
        practice_member_data_sorted: Dict[int, Dict[int, Dict[Any, Any]]] = {}

        # maping of practice id to member id to list of practice member history data
        practice_member_history_data_sorted: Dict[int, Dict[int, List[Dict[Any, Any]]]] = {}

        for entry in practice_member_data:
            practice_member_data_sorted.setdefault(entry['practice_id'], {})[entry['member_id']] = dict(entry)

        for entry in practice_member_history_data:
            practice_member_history_data_sorted.setdefault(entry['practice_id'], {}).setdefault(
                entry['member_id'], []
            ).append(dict(entry))

        for entry in practice_data:
            # We need to create a practice from this
            practice = Practice(bot=self, data=dict(entry))

            # Add our members
            members = practice_member_data_sorted.get(practice.id, {})
            for practice_member_data in members.values():
                member = practice._add_member(practice_member_data)

                # Let's get the history for this member now
                practice_history = practice_member_history_data_sorted.get(practice.id, {}).get(member.id, [])
                for element in practice_history:
                    member._add_history(element)

    # Events
    async def on_ready(self) -> None:
        """|coro|

        Called when the client has hit READY. Please note this can be called more than once during the clients
        uptime.
        """
        _log.info(f"Logged in as {self.user.name}")
        _log.info(
            f'Connected to {len(self.guilds)} servers total watching over {sum(list(m_count for g in self.guilds if (m_count := g.member_count))):,} members.'
        )
        _log.info(f'Invite link: {discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(0))}')

    # Helper utilities
    def safe_connection(self, *, timeout: Optional[float] = 10.0) -> DbContextManager:
        """A context manager that will acquire a Connection from the bot's pool.

        This will neatly manage the Connection and release it back to the pool when the context is exited.

        .. code-block:: python3

            async with bot.safe_connection(timeout=10) as connection:
                await connection.execute('SELECT 1')
        """
        return DbContextManager(self, timeout=timeout)

    def create_task(self, coro: Coroutine[T, Any, Any], *, name: Optional[str] = None) -> asyncio.Task[T]:
        """Create a task from a coroutine object.

        Parameters
        ----------
        coro: :class:`~asyncio.Coroutine`
            The coroutine to create the task from.
        name: Optional[:class:`str`]
            The name of the task.

        Returns
        -------
        :class:`~asyncio.Task`
            The task that was created.
        """

        return self.loop.create_task(coro, name=name)

    def wrap(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> asyncio.Future[T]:
        """|coro|

        A helper function to bind blocking cpu bound functions to the event loop to make them not blocking.


        Parameters
        ----------
        func: Callable[P, T]
            The function to wrap.
        *args: P.args
            The arguments to pass to the function.
        **kwargs: P.kwargs
            The keyword arguments to pass to the function.

        Returns
        -------
        asyncio.Future[T]
            The future that will be resolved when the function is done.
        """
        return self.loop.run_in_executor(self.thread_pool, functools.partial(func, *args, **kwargs))

    @wrap_extension
    async def load_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().load_extension(name, package=package)

    @wrap_extension
    async def reload_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().reload_extension(name, package=package)

    @wrap_extension
    async def unload_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().unload_extension(name, package=package)
