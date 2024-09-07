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
import inspect
import logging
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
)

import asyncpg
import discord
from discord.ext import commands
from typing_extensions import Concatenate, Self

from cogs.images import ApproveOrDenyImage, ImageRequest
from cogs.teams import Team
from cogs.teams.practices import Practice
from cogs.teams.scrims import Scrim, ScrimStatus
from utils import (
    BYPASS_SETUP_HOOK,
    BYPASS_SETUP_HOOK_CACHE_LOADING,
    RUNNING_DEVELOPMENT,
    START_TIMER_MANAGER,
    Context,
    ErrorHandler,
    GuildProfanityFinder,
    TimerManager,
    _parse_environ_boolean,
    parse_initial_extensions,
)

if TYPE_CHECKING:
    import datetime

    import aiohttp

T = TypeVar("T")
P = ParamSpec("P")
PoolType: TypeAlias = "asyncpg.Pool[asyncpg.Record]"
ConnectionType: TypeAlias = "asyncpg.Connection[asyncpg.Record]"
DecoFunc: TypeAlias = Callable[Concatenate["FuryBot", P], Coroutine[T, Any, Any]]
CacheFunc: TypeAlias = Callable[Concatenate["FuryBot", ConnectionType, P], Coroutine[Any, Any, T]]

_log = logging.getLogger(__name__)
if RUNNING_DEVELOPMENT:
    _log.setLevel(logging.DEBUG)

initial_extensions: Tuple[str, ...] = (
    "cogs.events.notifier",
    "cogs.fun",
    "cogs.images",
    "cogs.message_tracking",
    "cogs.moderation",
    "cogs.owner",
    "cogs.teams",
    "cogs.teams.practices",
    "cogs.meta",
    "cogs.teams.scrims",
    "jishaku",
    "utils.error_handler",
)


def cache_loader(
    flag_name: str,
) -> Callable[[CacheFunc[P, T]], CacheFunc[P, Optional[T]]]:
    def wrapped(func: CacheFunc[P, T]) -> CacheFunc[P, Optional[T]]:
        @functools.wraps(func)
        async def call_func(self: FuryBot, connection: ConnectionType, *args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            flag = _parse_environ_boolean(f"{flag_name}_CACHE")
            if not flag:
                return None

            _log.info("Loading %s cache from func %s", flag_name, func.__name__)

            return await func(self, connection, *args, **kwargs)

        call_func.__cache_loader__ = True  # type: ignore

        return call_func

    return wrapped


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
    """A simple context manager used to manage database connections.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    timeout: :class:`float`
        The timeout for acquiring a connection.
    """

    __slots__: Tuple[str, ...] = (
        "bot",
        "timeout",
        "_pool",
        "_Connection",
        "_tr",
        "_connection",
    )

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
        self,
        exc_type: Optional[Type[Exception]],
        exc: Optional[Exception],
        tb: Optional[Type[Exception]],
    ) -> None:
        if exc and self._tr:
            await self._tr.rollback()

        elif not exc and self._tr:
            await self._tr.commit()

        if self._connection:
            await self._pool.release(self._connection)  # type: ignore


class FuryBot(commands.Bot):
    """The main fury bot instance. This bot subclass contains many useful utilities
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

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        session: aiohttp.ClientSession,
        pool: PoolType,
    ) -> None:
        self.loop: asyncio.AbstractEventLoop = loop
        self.session: aiohttp.ClientSession = session
        self.pool: PoolType = pool
        self.thread_pool: futures.ThreadPoolExecutor = futures.ThreadPoolExecutor(max_workers=20)
        self.load_time = discord.utils.utcnow()

        self.timer_manager: Optional[TimerManager] = None
        if START_TIMER_MANAGER:
            self.timer_manager = TimerManager(bot=self)

        # Mapping[guild_id, Mapping[team_id, Team]]
        self._team_cache: Dict[int, Dict[int, Team]] = {}

        # Mapping[guild_id, Mapping[scrim_id, Scrim]
        self._team_scrim_cache: Dict[int, Dict[int, Scrim]] = {}

        # Mapping[guild_id, Mapping[team_id, Mapping[practice_id, Practice]]]
        self._team_practice_cache: Dict[int, Dict[int, Dict[int, Practice]]] = {}

        self.global_profanity_finder: Optional[GuildProfanityFinder] = None

        # Mapping[guild_id, GuildProfanityFinder]
        self.guild_profanity_finders: Dict[int, GuildProfanityFinder] = {}

        super().__init__(
            command_prefix=commands.when_mentioned_or("trev.", "trev"),
            help_command=None,
            description="A helpful moderation tool",
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
            The Postgres connection URI.
        **kwargs:
            Extra keyword arguments to pass to :meth:`asyncpg.create_pool`.
        """

        def _encode_jsonb(value: Dict[Any, Any]) -> str:
            return discord.utils._to_json(value)

        def _decode_jsonb(value: str) -> Dict[Any, Any]:
            return discord.utils._from_json(value)

        old_init = kwargs.pop("init", None)

        async def init(con: asyncpg.Connection[asyncpg.Record]) -> None:
            await con.set_type_codec(
                "jsonb",
                schema="pg_catalog",
                encoder=_encode_jsonb,
                decoder=_decode_jsonb,
                format="text",
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
        type: Literal["rich", "image", "video", "gifv", "article", "link"] = "rich",
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        timestamp: Optional[datetime.datetime] = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
    ) -> discord.Embed:
        """Get an instance of the bot's global :class:`discord.Embed` with the default
        bot's color, "FurBot blue".

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
            title=title,
            description=description,
            url=url,
            color=color,
            colour=colour,
            type=type,
            timestamp=timestamp,
        )

        if not colour and not color:
            embed.colour = discord.Colour.from_str("0x4EDBFC")

        if author:
            embed.set_author(name=author.name, icon_url=author.display_avatar.url)

        return embed

    # Management for custom profanity filters
    def get_profanity_finder(self, guild_id: int, /) -> Optional[GuildProfanityFinder]:
        custom_finder = self.guild_profanity_finders.get(guild_id, None)
        if custom_finder is not None:
            return custom_finder

        return self.global_profanity_finder

    def add_custom_profanity_finder(self, guild_id: int, finder: GuildProfanityFinder, /):
        self.guild_profanity_finders[guild_id] = finder

    def remove_custom_profanity_finder(self, guild_id: int, /) -> Optional[GuildProfanityFinder]:
        return self.guild_profanity_finders.pop(guild_id, None)

    # Team management
    def get_teams(self, guild_id: int, /) -> List[Team]:
        """Get all teams in a guild.

        Parameters
        ----------
        guild_id: :class:`int`
            The guild ID to get teams from.

        Returns
        -------
        List[:class:`Team`]
            The teams in the guild.
        """
        return list(self._team_cache.get(guild_id, {}).values())

    def get_team(self, team_id: int, /, *, guild_id: int) -> Optional[Team]:
        """Get a team from a guild.

        Parameters
        ----------
        team_id: :class:`int`
            The team ID to get.
        guild_id: :class:`int`
            The guild ID to get the team from.

        Returns
        -------
        Optional[:class:`Team`]
            The team, if it exists.
        """
        return self._team_cache.get(guild_id, {}).get(team_id)

    def get_team_from_channel(self, channel_id: int, guild_id: int, /) -> Optional[Team]:
        return Team.from_channel(channel_id, guild_id, bot=self)

    def add_team(self, team: Team, /) -> None:
        """Add a team to the cache.

        Parameters
        ----------
        team: :class:`Team`
            The team to add.
        """
        self._team_cache.setdefault(team.guild_id, {})[team.id] = team

    def remove_team(self, team_id: int, guild_id: int, /) -> Optional[Team]:
        """Remove a team from the cache.

        Parameters
        ----------
        team_id: :class:`int`
            The team ID to remove.
        guild_id: :class:`int`
            The guild ID to remove the team from.

        Returns
        -------
        Optional[:class:`Team`]
            The team that was removed, if it existed.
        """
        return self._team_cache.get(guild_id, {}).pop(team_id, None)

    # Scrim Management
    def get_scrim(self, scrim_id: int, guild_id: int, /) -> Optional[Scrim]:
        """Get a scrim from a guild.

        Parameters
        ----------
        scrim_id: :class:`int`
            The scrim ID to get.
        guild_id: :class:`int`
            The guild ID to get the scrim from.

        Returns
        -------
        Optional[:class:`Scrim`]
            The scrim, if it exists.
        """
        return self._team_scrim_cache.get(guild_id, {}).get(scrim_id)

    def add_scrim(self, scrim: Scrim, /) -> None:
        """Add a scrim to the cache.

        Parameters
        ----------
        scrim: :class:`Scrim`
            The scrim to add.
        """
        self._team_scrim_cache.setdefault(scrim.guild_id, {})[scrim.id] = scrim

    def remove_scrim(self, scrim_id: int, guild_id: int, /) -> Optional[Scrim]:
        """Remove a scrim from the cache.

        Parameters
        ----------
        scrim_id: :class:`int`
            The scrim ID to remove.
        guild_id: :class:`int`
            The guild ID to remove the scrim from.

        Returns
        -------
        Optional[:class:`Scrim`]
            The scrim that was removed, if it existed.
        """
        return self._team_scrim_cache.get(guild_id, {}).pop(scrim_id, None)

    def get_scrims_for(self, team_id: int, guild_id: int, /) -> List[Scrim]:
        """Get all scrims for the given team in the given guild.

        Parameters
        ----------
        team_id: :class:`int`
            The team ID to get scrims for.
        guild_id: :class:`int`
            The guild ID to get scrims from.

        Returns
        -------
        List[:class:`Scrim`]
            The scrims for the team in the guild.
        """
        guild_scrims = self._team_scrim_cache.get(guild_id)
        if guild_scrims is None:
            return []

        scrims: List[Scrim] = []
        for scrim in guild_scrims.values():
            if team_id in {scrim.home_id, scrim.away_id}:
                scrims.append(scrim)

        return scrims

    # Practice Management
    def get_practice(self, practice_id: int, team_id: int, guild_id: int, /) -> Optional[Practice]:
        """Get a practice from a guild.

        Parameters
        ----------
        practice_id: :class:`int`
            The practice ID to get.
        team_id: :class:`int`
            The team ID to get the practice from.
        guild_id: :class:`int`
            The guild ID to get the practice from.

        Returns
        -------
        Optional[:class:`Practice`]
            The practice, if it exists.
        """
        return self._team_practice_cache.get(guild_id, {}).get(team_id, {}).get(practice_id)

    def get_practices(self, guild_id: int, /) -> List[Practice]:
        """Get all practices in a guild.

        Parameters
        ----------
        List[:class:`Practice`]
            The practices in the guild.
        """
        guild_practices = self._team_practice_cache.get(guild_id, {})

        practices: List[Practice] = []
        for team_practices in guild_practices.values():
            practices.extend(team_practices.values())

        return practices

    def add_practice(self, practice: Practice) -> None:
        """Add a practice to the cache.

        Parameters
        ----------
        practice: :class:`Practice`
            The practice to add.
        """
        self._team_practice_cache.setdefault(practice.guild_id, {}).setdefault(practice.team_id, {})[practice.id] = practice

    def remove_practice(self, practice_id: int, team_id: int, guild_id: int, /) -> Optional[Practice]:
        """Remove a practice from the cache.

        Parameters
        ----------
        practice_id: :class:`int`
            The practice ID to remove.
        team_id: :class:`int`
            The team ID to remove the practice from.
        guild_id: :class:`int`
            The guild ID to remove the practice from.

        Returns
        -------
        Optional[:class:`Practice`]
            The practice that was removed, if it existed.
        """
        return self._team_practice_cache.get(guild_id, {}).get(team_id, {}).pop(practice_id, None)

    def clear_practices_for(self, team_id: int, guild_id: int, /) -> None:
        """Clear all practices for a team in a guild.

        Parameters
        ----------
        team_id: :class:`int`
            The team ID to clear practices for.
        guild_id: :class:`int`
            The guild ID to clear practices from.
        """
        self._team_practice_cache.get(guild_id, {}).pop(team_id, None)

    def get_practices_for(self, team_id: int, guild_id: int, /) -> List[Practice]:
        """Get all practices for the given team in the given guild.

        Parameters
        ----------
        team_id: :class:`int`
            The team ID to get practices for.
        guild_id: :class:`int`
            The guild ID to get practices from.

        Returns
        -------
        List[:class:`Practice`]
            The practices for the team in the guild.
        """
        guild_practices = self._team_practice_cache.get(guild_id)
        if guild_practices is None:
            return []

        return list(guild_practices.get(team_id, {}).values())

    # Events
    async def on_ready(self) -> None:
        """|coro|

        Called when the client has hit READY. Please note this can be called more than once during the clients
        uptime.
        """
        _log.info(f"Logged in as {self.user.name}")
        _log.info(
            f"Connected to {len(self.guilds)} servers total watching over {sum(list(m_count for g in self.guilds if (m_count := g.member_count))):,} members."
        )
        _log.info(f"Invite link: {discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(0))}")

    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        """|coro|

        Called when a member has been removed from a specific guild. This event listener will delete this member
        from any team they're on as to not allow members not in the server to appear on teams.

        Parameters
        ----------
        payload: :class:`discord.RawMemberRemoveEvent`
            The payload for the event.
        """
        teams = self.get_teams(payload.guild_id)
        if not teams:
            return

        for team in teams:
            member = team.get_member(payload.user.id)
            if member is not None:
                await member.remove_from_team()

    async def get_context(
        self,
        origin: Union[discord.Message, discord.Interaction[Self]],  # cls: Type[commands.Context[Self]] = Context
    ) -> Context:
        return await super().get_context(origin, cls=Context)

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

    @wrap_extension  # type: ignore
    async def load_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().load_extension(name, package=package)

    @wrap_extension  # type: ignore
    async def reload_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().reload_extension(name, package=package)

    @wrap_extension  # type: ignore
    async def unload_extension(self, name: str, /, *, package: Optional[str] = None) -> None:
        return await super().unload_extension(name, package=package)

    @cache_loader("TEAMS")  # type: ignore
    async def _cache_setup_teams(self, connection: ConnectionType) -> None:
        team_data = await connection.fetch("SELECT * FROM teams.settings")
        team_members_data = await connection.fetch("SELECT * FROM teams.members")

        team_member_mapping: Dict[int, List[Dict[Any, Any]]] = {}
        for entry in team_members_data:
            team_member_mapping.setdefault(entry["team_id"], []).append(dict(entry))

        for row in team_data:
            members = team_member_mapping.get(row["id"], [])
            team = await Team.from_record(dict(row), members, bot=self)
            self._team_cache.setdefault(team.guild_id, {})[team.id] = team

    @cache_loader("SCRIMS")  # type: ignore
    async def _cache_setup_scrims(self, connection: ConnectionType) -> None:
        scrim_records = await connection.fetch("SELECT * FROM teams.scrims")

        for entry in scrim_records:
            data = dict(entry)
            data["status"] = ScrimStatus(data["status"])

            scrim = Scrim(self, **data)
            scrim.load_persistent_views()
            self._team_scrim_cache.setdefault(scrim.guild_id, {})[scrim.id] = scrim

    async def _load_image_request(self, data: asyncpg.Record) -> None:
        await self.wait_until_ready()

        guild = self.get_guild(data["guild_id"])
        if not guild:
            return

        channel = guild.get_channel(data['channel_id'])
        if not channel:
            return

        attachment_data = data['attachment_payload']
        requester = guild.get_member(data['requester_id']) or await guild.fetch_member(data['requester_id'])

        request = ImageRequest(
            requester=requester,
            attachment=discord.Attachment(data=attachment_data, state=self._connection),
            channel=channel,
            message=data["message"],
            id=data["id"],
        )

        view = ApproveOrDenyImage(self, request)
        self.add_view(view, message_id=data["message_id"])

    @cache_loader("IMAGE_REQUESTS")  # type: ignore
    async def _cache_setup_image_requests(self, connection: ConnectionType) -> None:
        image_requests = await connection.fetch(
            "SELECT * FROM images.requests WHERE denied_reason IS NULL OR message_id IS NULL;"
        )
        for request in image_requests:
            self.create_task(self._load_image_request(request))

    @cache_loader("PRACTICES")  # type: ignore
    async def _cache_setup_practices(self, connection: ConnectionType) -> None:
        practice_data = await connection.fetch("SELECT * FROM teams.practice")
        practice_member_data = await connection.fetch("SELECT * FROM teams.practice_member")
        practice_member_history_data = await connection.fetch("SELECT * FROM teams.practice_member_history")

        # Sort the member data to be {practice_id: {member_id: data}} because we can have more than one member per practice
        practice_member_mapping: Dict[int, Dict[int, Dict[Any, Any]]] = {}
        for entry in practice_member_data:
            practice_member_mapping.setdefault(entry["practice_id"], {})[entry["member_id"]] = dict(entry)

        # Sort the member history data to be {practice_id: {member_id: List[data]}} because we an have more than one
        # history entry per member per practice
        practice_member_history_mapping: Dict[int, Dict[int, List[Dict[Any, Any]]]] = {}
        for entry in practice_member_history_data:
            practice_member_history_mapping.setdefault(entry["practice_id"], {}).setdefault(entry["member_id"], []).append(
                dict(entry)
            )

        for entry in practice_data:
            # We need to create a practice from this
            practice = Practice(bot=self, data=dict(entry))

            member_data = practice_member_mapping.get(practice.id, {})
            for data in member_data.values():
                member = practice._add_member(dict(data))

                member_practice_history = practice_member_history_mapping.get(practice.id, {}).get(member.member_id, [])
                for history_entry in member_practice_history:
                    member._add_history(dict(history_entry))

            self._team_practice_cache.setdefault(practice.guild_id, {}).setdefault(practice.team_id, {})[
                practice.id
            ] = practice

    @cache_loader("PROFANITY_FILTER")  # type: ignore
    async def _cache_setup_profanity_filter(self, connection: ConnectionType) -> None:
        pattern = await GuildProfanityFinder.get_default_pattern()
        self.global_profanity_finder = GuildProfanityFinder(pattern, guild_id=None)

    # Hooks
    async def setup_hook(self) -> None:
        if BYPASS_SETUP_HOOK:
            return

        extensions_to_load = parse_initial_extensions(initial_extensions)

        await asyncio.gather(*(self.load_extension(ext) for ext in extensions_to_load))

        if BYPASS_SETUP_HOOK_CACHE_LOADING:
            _log.info("Bypassing cache loading.")
            return

        cache_loading_functions: List[Tuple[str, Callable[..., Coroutine[Any, Any, Any]]]] = [
            item
            for item in inspect.getmembers(self, predicate=inspect.iscoroutinefunction)
            if getattr(item[1], "__cache_loader__", None)
        ]

        _log.info(f"Loading {len(cache_loading_functions)} cache entries.")

        async def _wrapped_cache_loader(
            cache_loading_function: Callable[..., Coroutine[Any, Any, Any]],
        ) -> None:
            async with self.safe_connection() as connection:
                try:
                    await cache_loading_function(connection=connection)
                except Exception as exc:
                    _log.warning(
                        f"Failed to load cache entry {cache_loading_function.__name__}.",
                        exc_info=exc,
                    )

        await asyncio.gather(*[_wrapped_cache_loader(func) for _, func in cache_loading_functions])
