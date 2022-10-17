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
import datetime
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypeVar, Union

import asyncpg
import discord

from .errors import TimerNotFound

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot


if TYPE_CHECKING:

    JSONValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
    JSONType = Union[JSONValue, Dict[str, JSONValue], List[JSONValue]]


__all__: Tuple[str, ...] = ('Timer', 'TimerManager')

T = TypeVar('T')

_log = logging.getLogger('FuryBot.utils.timer')


class Timer:
    """Represents a Timer within the database.

    .. container:: operations

        .. describe:: x == y

            Determines if the Timer is equal to another Timer.

        .. describe:: x != y

            Determines if the Timer is not equal to another Timer.

        .. describe:: hash(x)

            Returns the hash of the Timer.

        .. describe:: repr(x)

            Returns the string representation of the Timer.

    Attributes
    ----------
    args: List[Any]
        A list of arguments to pass to the :meth:`TimerManager.create_timer` method.
    kwargs: Dict[Any, Any]
        A dictionary of keyword arguments to pass to the :meth:`TimerManager.create_timer` method.
    precise: :class:`bool`
        Whether or not to dispatch the timer listener with the timer's args and kwargs. If ``False``, only
        the timer will be passed to the listener.
    event: :class:`str`
        The event to trigger when the timer expires. The listener can be formatted as so: ``on_{timer.event}_timer_complete``
    created_at: :class:`datetime.datetime`
        The time the timer was created.
    expires: :class:`datetime.datetime`
        The time the timer expires.
    """

    __slots__: Tuple[str, ...] = (
        'args',
        'kwargs',
        'precise',
        'event',
        'id',
        'created_at',
        'expires',
        '_cs_event_name',
        'member',
        '_extra',
        'bot',
    )

    if TYPE_CHECKING:
        member: Optional[discord.Member]

    def __init__(self, *, record: asyncpg.Record, bot: FuryBot) -> None:
        self.bot: FuryBot = bot

        self.id: int = record['id']

        extra: Dict[str, Any] = record['extra']
        self._extra = extra
        self.args: List[Any] = extra.get('args', [])
        self.kwargs: Dict[str, Any] = extra.get('kwargs', {})
        self.precise: bool = record['precise']

        self.event: str = record['event']
        self.created_at: datetime.datetime = record['created']
        self.expires: datetime.datetime = record['expires']

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timer):
            return False

        return self.id == other.id

    def __ne__(self, _o: object) -> bool:
        return not self.__eq__(_o)

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f'<Timer created={self.created_at!r} expires={self.expires!r} event={self.event!r}>'

    @discord.utils.cached_slot_property('_cs_event_name')
    def event_name(self) -> str:
        """:class:`str`: Returns the timer's event name."""
        return f'{self.event}_timer_complete'

    async def move_to_storage(self, bot: FuryBot, connection: Optional[ConnectionType] = None) -> None:
        """This function moves the timer into timer stoage.

        Parameters
        ----------
        bot: :class:`FuryBot`
            The bot instance.
        connection : Optional[ConnectionType]
            An optional connection to use.
        """
        # Inserting data into the database.
        query = 'INSERT INTO timer_storage (event, extra, created, expires, precise) VALUES($1, $2, $3, $4, $5)'
        args = (self.event, self._extra, self.created_at, self.expires, self.precise)

        if connection is None:
            async with bot.safe_connection() as conn:
                await conn.execute(query, *args)
        else:
            await connection.execute(query, *args)

    async def delete(self, connection: Optional[ConnectionType] = None) -> None:
        """|coro|

        Delete the timer.

        Parameters
        ----------
        connection: Optional[:class:`asyncpg.Connection`]
            An optional connection to use.

        Raises
        ------
        TimerNotFound
            A timer with that ID does not exist, so there is nothing
            to delete.
        """
        if not connection:
            async with self.bot.safe_connection() as conn:
                data = await conn.fetchrow('SELECT * FROM timers WHERE id = $1', self.id)
                if not data:
                    raise TimerNotFound(self.id)

                await conn.execute(f'DELETE FROM timers WHERE id = $1', self.id)
        else:
            data = await connection.fetchrow('SELECT * FROM timers WHERE id = $1', self.id)
            if not data:
                raise TimerNotFound(self.id)

            await connection.execute(f'DELETE FROM timers WHERE id = $1', self.id)


class TimerManager:
    """A class used to create and manage timers.

    Please note this can be inherited in a cog to allow for easy
    timer management.

    Attributes
    ----------
    bot: :class:`~.FuryBot`
        The bot instance.
    """

    __slots__: Tuple[str, ...] = ('bot', '_have_data', '_current_timer', '_task', '_cs_display_emoji')

    def __init__(self, *, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self._task: asyncio.Task[None] = bot.loop.create_task(self.dispatch_timers())
        self._have_data = asyncio.Event()
        self._current_timer: Optional[Timer] = None

    @discord.utils.cached_slot_property('_cs_display_emoji')
    def display_emoji(self) -> discord.PartialEmoji:
        """:class:`discord.PartialEmoji`: The emoji to display when a timer is dispatched."""
        return discord.PartialEmoji(name='\N{ALARM CLOCK}')

    async def get_active_timer(self, *, connection: Optional[ConnectionType] = None, days: int = 7) -> Optional[Timer]:
        """|coro|

        Called to get the most current active timer in the database. This timer is expired and should be dispatched.

        Parameters
        ----------
        connection: Optional[:class:`asyncpg.Connection`]
            The connection to use.
        days: :class:`int`
            The number of days to look back.

        Returns
        -------
        Optional[:class:`Timer`]
            The timer that is expired and should be dispatched.
        """
        query = f"SELECT * FROM timers WHERE (expires IS NOT NULL AND expires < (CURRENT_DATE + $1::interval)) ORDER BY expires LIMIT 1;"
        con = connection or self.bot.pool

        record = await con.fetchrow(query, datetime.timedelta(days=days))
        return Timer(record=record, bot=self.bot) if record else None

    async def wait_for_active_timers(self, *, days: int = 7) -> Optional[Timer]:
        """|coro|

        Waity for a timer that has expired. This will wait until a timer is expired and should be dispatched.

        Parameters
        ----------
        days: :class:`int`
            The number of days to look back.

        Returns
        -------
        :class:`Timer`
            The timer that is expired and should be dispatched.
        """
        # Please note the return value in the doc is different than the one in the function.
        # This function actually only returns a Timer but pyright doesn't like typehinting that.
        async with self.bot.safe_connection() as con:
            timer = await self.get_active_timer(connection=con, days=days)
            if timer is not None:
                self._have_data.set()
                return timer

            self._have_data.clear()
            self._current_timer = None
            await self._have_data.wait()
            return await self.get_active_timer(connection=con, days=days)

    async def call_timer(self, timer: Timer) -> None:
        """Call an expired timer to dispatch it.

        Parameters
        ----------
        timer: :class:`Timer`
            The timer to dispatch.
        """
        try:
            await timer.delete()
        except TimerNotFound:
            # We don't want to call a
            # timer that was deleted.
            return

        await timer.move_to_storage(self.bot)

        if timer.precise:
            self.bot.dispatch(timer.event_name, *timer.args, **timer.kwargs)
        else:
            self.bot.dispatch(timer.event_name, timer)

    async def dispatch_timers(self):
        """|coro|

        The main dispatch loop. This will wait for a timer to expire and dispatch it.
        Please note if you use this class, you need to cancel the task when you're done
        with it.
        """
        try:
            while not self.bot.is_closed():
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                if not timer:
                    _log.warning('Timer was supposted to be here, but isn\'t.. oh no.')
                    return

                now = datetime.datetime.utcnow()
                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            if self._task:
                self._task.cancel()
                self._task = self.bot.create_task(self.dispatch_timers())

    async def create_timer(
        self,
        when: datetime.datetime,
        event: str = 'timer',
        *args: JSONType,
        now: Optional[datetime.datetime] = None,
        precise: bool = True,
        **kwargs: JSONType,
    ) -> Timer:
        """|coro|

        Used to create a timer in the database and dispatch it.

        Parameters
        ----------
        when: :class:`datetime.datetime`
            When the timer should expire and be dispatched.
        event: :class:`str`
            The event to trigger when the timer expires. The listener can be formatted as so: ``on_{timer.event}_timer_complete``
        *args: List[Any]
            A list of arguments to be passed to :class:`Timer.args`. please note all items in this list
            must be JSON serializable.
        precise: :class:`bool`
            Whether or not to dispatch the timer listener with the timer's args and kwargs. If ``False``, only
            the timer will be passed to the listener. Defaults to ``True``.
        **kwargs: Dict[:class:`str`, Any]
            A dictionary of keyword arguments to be passed to :class:`Timer.kwargs`. Please note each element
            in this dictionary must be JSON serializable.
        """
        await self.bot.wait_until_ready()

        # Remove timezone information since the database does not deal with it
        when = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        now = (now or discord.utils.utcnow()).astimezone(datetime.timezone.utc).replace(tzinfo=None)

        delta = (when - now).total_seconds()
        query = f"""INSERT INTO timers (event, extra, expires, created, precise)
                   VALUES ($1, $2::jsonb, $3, $4, $5)
                   RETURNING *;
                """
        sanitized_args = (event, {'args': args, 'kwargs': kwargs}, when, now, precise)

        async with self.bot.safe_connection() as conn:
            row = await conn.fetchrow(query, *sanitized_args)

        assert row is not None

        # only set the data check if it can be waited on
        if delta <= (86400 * 40):  # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer.expires:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.create_task(self.dispatch_timers())

        timer = Timer(record=row, bot=self.bot)
        return timer

    async def get_timer(self, id: int) -> Timer:
        """|coro|

        Used to get a timer from it's ID.

        Parameters
        ----------
        id: :class:`int`
            The ID of the timer to get.

        Returns
        -------
        :class:`Timer`
            The timer that was fetched.

        Raises
        ------
        TimerNotFound
            A timer with that ID does not exist.
        """
        async with self.bot.safe_connection() as conn:
            data = await conn.fetchrow(f'SELECT * FROM timers WHERE id = $1', id)

        if not data:
            raise TimerNotFound(id)

        return Timer(record=data, bot=self.bot)

    async def fetch_timers(self) -> List[Timer]:
        """|coro|

        Used to fetch all timers from the database.

        Returns
        -------
        :class:`list`
            A list of :class:`Timer` objects.
        """
        async with self.bot.safe_connection() as conn:
            data = await conn.fetch(f'SELECT * FROM timers')

        return [Timer(record=row, bot=self.bot) for row in data]
