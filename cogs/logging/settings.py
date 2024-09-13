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
import dataclasses

import discord
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Type
from typing_extensions import Self

from utils import QueryBuilder

if TYPE_CHECKING:
    from bot import FuryBot, ConnectionType

MISSING = discord.utils.MISSING

# fmt: off
ALL_EVENTS: Set[str] = set([
    'automod_rule_create', 
    'automod_rule_update', 
    'automod_rule_delete', 
    'automod_action'
])
# fmt: on


@dataclasses.dataclass()
class LoggingEvent:
    id: int
    settings_id: int
    event_type: str

    settings: LoggingSettings

    @property
    def bot(self) -> FuryBot:
        return self.settings.bot

    @property
    def human_readable_event_type(self) -> str:
        return self.event_type.replace('_', ' ').title()

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                DELETE FROM logging.events
                WHERE id = $1;
                ''',
                self.id,
            )


class LoggingSettings:
    def __init__(self, *, data: Dict[str, Any], bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.guild_id: int = data['guild_id']

        # Denotes the logging channel ID, if set
        self.logging_channel_id: Optional[int] = data['logging_channel_id']

        # An internal mapping of logging events. Set during the bot's startup for
        # cache and updated automatically as needed.
        self._logging_events: Dict[str, LoggingEvent] = {}

    @classmethod
    async def create(cls: Type[Self], guild_id: int, /, *, bot: FuryBot) -> Self:
        async with bot.safe_connection() as connection:
            record = await connection.fetchrow(
                '''
                INSERT INTO logging.settings (guild_id)
                VALUES ($1)
                ON CONFLICT (guild_id) DO NOTHING
                RETURNING *;
                ''',
                guild_id,
            )
            assert record is not None, 'Failed to create logging settings.'

        instance = cls(data=dict(record), bot=bot)
        bot.add_logging_settings(instance)
        return instance

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def logging_channel(self) -> Optional[discord.TextChannel]:
        logging_channel_id = self.logging_channel_id
        if logging_channel_id is None:
            return None

        guild = self.guild
        if guild is None:
            return None

        channel = guild.get_channel(logging_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None

        return channel

    @property
    def logging_events(self) -> List[LoggingEvent]:
        return list(self._logging_events.values())

    def get_logging_event(self, event_type: str) -> Optional[LoggingEvent]:
        return self._logging_events.get(event_type)

    def add_logging_event(self, event: LoggingEvent) -> None:
        self._logging_events[event.event_type] = event

    def has_logging_event(self, event_type: str) -> bool:
        return event_type in self._logging_events

    def remove_logging_event(self, event_type: str) -> None:
        self._logging_events.pop(event_type, None)

    async def propagate_cache(self, *, connection: ConnectionType) -> None:
        self._logging_events.clear()

        records = await connection.fetch(
            '''
            SELECT *
            FROM logging.events
            WHERE settings_id = $1;
            ''',
            self.id,
        )

        for record in records:
            instance = LoggingEvent(**dict(record), settings=self)
            self.add_logging_event(instance)

    async def edit(self, *, logging_channel_id: Optional[int] = MISSING) -> None:
        builder = QueryBuilder('logging.settings')
        builder.add_condition('id', self.id)

        if logging_channel_id is not MISSING:
            self.logging_channel_id = logging_channel_id
            builder.add_arg('logging_channel_id', logging_channel_id)

        async with self.bot.safe_connection() as connection:
            await builder(connection=connection)

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                DELETE FROM logging.settings
                WHERE id = $1;
                ''',
                self.id,
            )

        self.bot.remove_logging_settings(self.guild_id)

    async def create_logging_event(self, *, event_type: str) -> LoggingEvent:
        if event_type in self._logging_events:
            return self._logging_events[event_type]

        async with self.bot.safe_connection() as connection:
            record = await connection.fetchrow(
                '''
                INSERT INTO logging.events (settings_id, event_type)
                VALUES ($1, $2)
                RETURNING *;
                ''',
                self.id,
                event_type,
            )
            assert record is not None, 'Failed to add logging event.'

        instance = LoggingEvent(**dict(record), settings=self)
        self.add_logging_event(instance)
        return instance

    async def delete_all_logging_events(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                DELETE FROM logging.events
                WHERE settings_id = $1;
                ''',
                self.id,
            )

        self._logging_events.clear()

    async def create_all_possible_logging_events(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.executemany(
                '''
                INSERT INTO logging.events (settings_id, event_type)
                VALUES ($1, $2);
                ''',
                [
                    (self.id, event)
                    for event in ALL_EVENTS
                    if event not in self._logging_events
                    if self.get_logging_event(event) is None
                ],
            )

            await self.propagate_cache(connection=connection)
