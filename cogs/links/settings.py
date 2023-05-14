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

import datetime
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

import discord
from typing_extensions import Self

from utils import QueryBuilder

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot

MISSING = discord.utils.MISSING


class AllowedLink:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.settings_id: int = data['settings_id']
        self.url: str = data['url']
        self.added_at: datetime.datetime = data['added_at']
        self.added_by_id: int = data['added_by_id']

    @property
    def added_by(self) -> Optional[discord.User]:
        return self.bot.get_user(self.added_by_id)


class LinkActionType(enum.Enum):
    warn = 'warn'
    mute = 'mute'
    surpress = 'surpress'


class LinkAction:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.settings_id: int = data['settings_id']
        self.type: LinkActionType = LinkActionType(data['type'])
        self.delta: Optional[datetime.timedelta] = datetime.timedelta(seconds=delta) if (delta := data['delta']) else None
        self.warn_message: Optional[str] = data['warn_message']

    @classmethod
    async def create(
        cls: Type[Self],
        *,
        bot: FuryBot,
        connection: ConnectionType,
        settings_id: int,
        type: LinkActionType,
        delta: Optional[datetime.timedelta] = None,
        warn_message: Optional[str] = None,
    ) -> Self:
        settings = bot.get_link_setting(settings_id)
        if settings is None:
            raise ValueError('No link settings found for guild_id')

        data = await connection.fetchrow(
            'INSERT INTO links.actions (settings_id, type, delta, warn_message) VALUES ($1, $2, $3, $4) RETURNING *',
            settings_id,
            type.value,
            delta,
            warn_message,
        )
        assert data

        self = cls(bot=bot, data=dict(data))
        settings.actions.append(self)

        return self

    @property
    def settings(self) -> Optional[LinkSettings]:
        return self.bot.get_link_setting(self.settings_id)

    async def edit(
        self,
        *,
        connection: ConnectionType,
        type: LinkActionType = MISSING,
        delta: datetime.timedelta = MISSING,
        warn_message: str = MISSING,
    ) -> None:
        builder = QueryBuilder('links.actions')
        builder.add_condition('id', self.id)

        if type is not MISSING:
            builder.add_arg('type', type.value)
            self.type = type

        if delta is not MISSING:
            builder.add_arg('delta', delta)
            self.delta = delta

        if warn_message is not MISSING:
            builder.add_arg('warn_message', warn_message)
            self.warn_message = warn_message

        await builder(connection)

    async def delete(self, *, connection: ConnectionType) -> None:
        await connection.execute('DELETE FROM links.actions WHERE id = $1', self.id)

        raise NotImplementedError


class LinkSettings:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.guild_id: int = data['guild_id']
        self.notifier_channel_id: Optional[int] = data['notifier_channel_id']
        self.actions: List[LinkAction] = []
        self.allowed_links: List[AllowedLink] = []

    @classmethod
    async def create(
        cls: Type[Self],
        *,
        bot: FuryBot,
        connection: ConnectionType,
        guild_id: int,
        notifier_channel_id: Optional[int] = None,
    ) -> Self:
        data = await connection.fetchrow(
            'INSERT INTO links.settings (guild_id, notifier_channel_id) VALUES ($1, $2) RETURNING *',
            guild_id,
            notifier_channel_id,
        )

        assert data

        self = cls(bot=bot, data=dict(data))
        bot.add_link_settings(self)

        return self

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def notifier_channel(self) -> Optional[discord.abc.GuildChannel]:
        if self.notifier_channel_id is None:
            return None

        guild = self.guild
        if guild is None:
            return None

        return guild.get_channel(self.notifier_channel_id)

    def add_action(self, action: LinkAction) -> None:
        self.actions.append(action)

    def remove_action(self, action: LinkAction) -> None:
        self.actions.remove(action)

    def add_allowed_link(self, link: AllowedLink) -> None:
        self.allowed_links.append(link)

    def remove_allowed_link(self, link: AllowedLink) -> None:
        self.allowed_links.remove(link)

    async def edit(self, *, connection: ConnectionType, notifier_channel_id: int = MISSING) -> None:
        builder = QueryBuilder('links.settings')
        builder.add_condition('id', self.id)

        if notifier_channel_id is not MISSING:
            builder.add_arg('notifier_channel_id', notifier_channel_id)
            self.notifier_channel_id = notifier_channel_id

        await builder(connection)

    async def create_link_action(
        self,
        *,
        connection: ConnectionType,
        type: LinkActionType,
        delta: Optional[datetime.timedelta] = None,
        warn_message: Optional[str] = None,
    ) -> LinkAction:
        return await LinkAction.create(
            bot=self.bot,
            connection=connection,
            settings_id=self.id,
            type=type,
            delta=delta,
            warn_message=warn_message,
        )