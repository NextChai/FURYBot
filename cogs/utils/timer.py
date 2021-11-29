import datetime
import asyncio
import asyncpg
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from . import time
    
class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires',  'member', 'dispatched')

    def __init__(self, *, record):
        self.id = record['id']

        extra = record['extra']
        self.args = extra.get('args', [])
        self.kwargs = extra.get('kwargs', {})
        self.event = record['event']
        self.created_at = record['created']
        self.expires = record['expires']
        self.member: int = record['member']
        self.dispatched: bool = record['dispatched']

    @classmethod
    def temporary(cls, *, member, expires, created, event, args, kwargs):
        pseudo = {
            'id': None,
            'extra': { 'args': args, 'kwargs': kwargs },
            'event': event,
            'created': created,
            'expires': expires,
            'member': member,
            'dispatched': None
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return time.format_relative(self.created_at)

    @property
    def author_id(self):
        if self.args:
            return int(self.args[0])
        return None

    def __repr__(self):
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'


class TimerHandler:
    def __init__(self, bot, name: str):
        self.name: str = name
        
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())
    
    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name='\N{ALARM CLOCK}')
    
    def cog_unload(self):
        self._task.cancel()
        
    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        if isinstance(error, commands.TooManyArguments):
            await ctx.send(f'You called the {ctx.command.name} command with too many arguments.')
            
    async def get_active_timer(self, *, connection=None, days=7):
        query = f"SELECT * FROM {self.name} WHERE (expires IS NOT NULL AND expires < (CURRENT_DATE + $1::interval)) AND dispatched IS $2 ORDER BY expires LIMIT 1;"
        con = connection or self.bot.pool

        record = await con.fetchrow(query, datetime.timedelta(days=days), False)
        return Timer(record=record) if record else None
    
    async def wait_for_active_timers(self, *, connection=None, days=7):
        async with self.bot.safe_connection() as con:
            timer = await self.get_active_timer(connection=con, days=days)
            if timer is not None:
                self._have_data.set()
                return timer

            self._have_data.clear()
            self._current_timer = None
            await self._have_data.wait()
            return await self.get_active_timer(connection=con, days=days)
        
    async def call_timer(self, timer):
        async with self.bot.safe_connection() as con:
            await con.execute(f"UPDATE {self.name} SET dispatched = $1 WHERE id = $2;", True, timer.id)
        
        event_name = f'{timer.event}_timer_complete'
        self.bot.dispatch(event_name, timer)
    
    async def dispatch_timers(self):
        try:
            while not self.bot.is_closed():
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                now = datetime.datetime.utcnow()

                if timer.expires >= now: # type: ignore
                    to_sleep = (timer.expires - now).total_seconds() # type: ignore
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError): 
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())
        
    async def create_timer(self, *args, **kwargs):
        r"""Creates a timer.
        
        Parameters
        -----------
        when: datetime.datetime
            When the timer should fire.
        event: str
            The name of the event to trigger.
            Will transform to 'on_{event}_timer_complete'.
        *args
            Arguments to pass to the event
        **kwargs
            Keyword arguments to pass to the event
        connection: asyncpg.Connection
            Special keyword-only argument to use a specific connection
            for the DB request.
        created: datetime.datetime
            Special keyword-only argument to use as the creation time.
            Should make the timedeltas a bit more consistent.
        Note
        ------
        Arguments and keyword arguments must be JSON serialisable.
        
        Returns
        --------
        :class:`Timer`
        """
        when, member, *args = args

        try:
            connection = kwargs.pop('connection')
        except KeyError:
            connection = self.bot.pool

        try:
            now = kwargs.pop('created')
        except KeyError:
            now = discord.utils.utcnow()
            
        # Remove timezone information since the database does not deal with it
        when = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        now = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        timer = Timer.temporary(member=member, event=self.name, args=args, kwargs=kwargs, expires=when, created=now)
        delta = (when - now).total_seconds()

        query = f"""INSERT INTO {self.name} (event, extra, expires, created, member)
                   VALUES ($1, $2::jsonb, $3, $4, $5)
                   RETURNING id;
                """

        row = await connection.fetchrow(query, self.name, { 'args': args, 'kwargs': kwargs }, when, now, member)
        timer.id = row[0]

        # only set the data check if it can be waited on
        if delta <= (86400 * 40): # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer.expires:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer