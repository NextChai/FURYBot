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
from concurrent import futures
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Literal,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
)

import asyncpg
import discord
from discord.ext import commands
from typing_extensions import Self

from utils import assertion
from utils.link import LinkFilter
from utils.profanity import ProfantiyFilter

if TYPE_CHECKING:
    import datetime

    import aiohttp

T = TypeVar('T')
P = ParamSpec('P')
PoolType: TypeAlias = 'asyncpg.Pool[asyncpg.Record]'
ConnectionType: TypeAlias = 'asyncpg.Connection[asyncpg.Record]'

_log = logging.getLogger(__name__)

initial_extensions: Tuple[str, ...] = (
    'jishaku',
)


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
        return await self.__aexit__(None, None, None)

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

    def __init__(self, *, loop: asyncio.AbstractEventLoop, session: aiohttp.ClientSession, pool: PoolType) -> None:
        self.loop: asyncio.AbstractEventLoop = loop
        self.session: aiohttp.ClientSession = session
        self.pool: PoolType = pool
        self.thread_pool: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(max_workers=20)

        self.profanity_filter: ProfantiyFilter = ProfantiyFilter(self)
        self.link_filter: LinkFilter = LinkFilter(self)
        
        super().__init__(
            command_prefix='fury.',
            help_command=None,
            description='A helpful moderation tool',
            intents=discord.Intents.all(),
            strip_after_prefix=True,
            allowed_mentions=discord.AllowedMentions.none(),
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
        return assertion(pool, PoolType)

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

    # Hooks
    async def setup_hook(self) -> None:
        return await super().setup_hook()

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
