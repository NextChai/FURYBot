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

import logging
import asyncio
import async_timeout
import datetime
from typing import TYPE_CHECKING, Any, Optional

import discord

from .db import Table, Row

if TYPE_CHECKING:
    from bot import FuryBot
    
log = logging.getLogger(__name__)
    

class TimerTable(Table, name='timers'):
    def __init__(self) -> None:
        super().__init__(keys=[
            Row('created_at', 'TIMESTAMP'),
            Row('expires_at', 'TIMESTAMP'),
            Row('extra', 'JSONB'),
            Row('member', 'BIGINT'),
            Row('channel', 'BIGINT'),
            Row('guild', 'BIGINT'),
            Row('moderator', 'BIGINT'),
            Row('id', 'BIGSERIAL'),
        ])


class TimerRow:
    __slots__ = ('bot', 'created_at', 'expires_at', 'extra', 'member_id', 'channel_id', 'guild_id', 'moderator_id', 'id')
    
    def __init__(self, bot: FuryBot, **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        
        self.created_at: datetime.datetime = kwargs.pop('created_at')
        self.expires_at: datetime.datetime = kwargs.pop('expires_at')
        self.extra: dict = kwargs.pop('extra')
        self.member_id: int = kwargs.pop('member')
        self.channel_id: int = kwargs.pop('channel')
        self.guild_id: int = kwargs.pop('guild')
        self.moderator_id: int = kwargs.pop('moderator')
        self.id: Optional[int] = kwargs.get('id')
    
    @property
    def channel(self) -> Optional[discord.abc.GuildChannel]:
        return self.bot.get_channel(self.channel_id)
    
    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild)
    
    @property
    def member(self) -> Optional[discord.Member]:
        guild = self.guild
        if not guild:
            return None
        
        return guild.get_member(self.member_id)
    
    async def get_member(self) -> discord.Member:
        member = self.member
        if member:
            return member
        
        guild = self.guild
        if guild is None:
            raise Exception('Guild was none!')
        
        member = await guild.fetch_member(self.member_id)
        return member
    
        

class Timer:
    """Used to handle a "Timer". Will do operations based upon 
    a time set within the database.
    
    We'll subclass this to handle different types of timers.
    """
    def __init__(self, table: Table, bot: FuryBot) -> None:
        self.table: Table = table
        self.bot: FuryBot = bot
        bot.loop.create_task(self.create_table())
        
        self._event: asyncio.Event = asyncio.Event(loop=bot.loop)
        self._task = bot.loop.create_task(self.send_events())
        self._current: Optional[TimerRow] = None
        
    async def get_row(self, member: discord.Member) -> Optional[TimerRow]:
        query = f"""
            SELECT * FROM {self.table.qualified_name} 
            WHERE member = $1;
        """
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(query, member.id)
            log.info(f'{self.table.qualified_name} - {data}')
        
        return TimerRow(self.bot, **data) if data else None
    
    async def create_table(self) -> None:
        async with self.bot.safe_connection() as connection:
            query = self.table.create_string()
            exc = await connection.execute(query)
            log.info(f'{self.table.qualified_name} - {exc}')
            
    async def insert_row(self, **kwargs) -> None:
        query = f"""
            INSERT INTO {self.table.qualified_name} (created_at, expires_at, extra, member, channel, guild, moderator) 
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        """
        
        timer = TimerRow(self.bot, **kwargs)
        async with self.bot.safe_connection() as connection:
            await connection.fetchrow(
                query,
                timer.created_at,
                timer.expires_at,
                timer.extra,
                timer.member_id,
                timer.channel_id,
                timer.guild_id,
                timer.moderator_id
            )
        
        # No matter what happens here,
        # we need to re-call send_events to check if this new packet is either:
        # 1. The first packet in the queue
        # 2. The closest packet in the queue
        
        self._task.cancel()
        self._task = self.bot.loop.create_task(self.send_events())
    
    async def get_expired_row(self) -> Optional[TimerRow]:
        async with self.bot.safe_connection() as connection:
            query = f'SELECT * FROM {self.table.qualified_name} WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;'
            data = await connection.fetchrow(query, datetime.timedelta(days=40))
        
        return TimerRow(self.bot, **data) if data else None
    
    async def get_closest_row(self) -> TimerRow:
        row = await self.get_expired_row()
        
        if row:
            self._event.set()
            self._current = row
            return row
            
        self._event.clear()
        self._current = None
        
        try:
            # I'm adding the async timeout for a very specific reason.
            # If a user adds a packet more than 40 days out, and the bot's uptime is more than 40 days,
            # and no other user uses the command, the event wont get distrubuted. This fixes that.
            async with async_timeout(3600, loop=self.bot.loop):
                await self._event.wait()
        except asyncio.TimeoutError: 
            pass
        
        # If we get here we couldn't get a packet.
        # Due to this, let's re-call get_closest_row and try again.
        return await self.get_closest_row()
    
    async def distrubute_event(self, row: TimerRow) -> None:
        async with self.bot.safe_connection() as connection:
            query = f'DELETE FROM {self.table.qualified_name} WHERE id = $1;'
            await connection.execute(query, row.id)
        
        member = await row.get_member()
        return await self.dispatch(member, row)
    
    async def send_events(self) -> None:
        await self.bot.wait_until_ready()
        
        try:
            while not self.bot.is_closed():
                row = await self.get_closest_row()
                now = datetime.datetime.utcnow()
                
                if row.expires_at > now:
                    sleeptime = (row.expires_at - now).total_seconds()
                    await asyncio.sleep(sleeptime)
                
                await self.distrubute_event(row)
        except discord.ConnectionClosed:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.send_events())   
            
    async def dispatch(self, member: discord.Member, row: TimerRow) -> Any:
        raise NotImplementedError()
    
