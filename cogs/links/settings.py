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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

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

    @classmethod
    async def create(
        cls: Type[Self],
        *,
        bot: FuryBot,
        connection: ConnectionType,
        settings_id: int,
        url: str,
        added_at: datetime.datetime,
        added_by_id: int,
    ) -> Self:
        settings = bot.get_link_setting(settings_id)
        if settings is None:
            raise ValueError('No link settings found for guild_id')

        data = await connection.fetchrow(
            'INSERT INTO links.allowed_links (settings_id, url, added_at, added_by_id) '
            'VALUES ($1, $2, $3, $4 '
            'RETURNING *',
            settings_id,
            url,
            added_at,
            added_by_id,
        )
        assert data

        self = cls(bot=bot, data=dict(data))
        settings.add_allowed_link(self)

        return self

    @property
    def added_by(self) -> Optional[discord.User]:
        return self.bot.get_user(self.added_by_id)

    @property
    def settings(self) -> Optional[LinkSettings]:
        return self.bot.get_link_setting(self.settings_id)

    async def delete(self, *, connection: ConnectionType) -> None:
        await connection.execute('DELETE FROM links.allowed_links WHERE id = $1', self.id)

        # Need to remove this allowed link from the settings
        settings = self.settings
        if settings is None:
            return

        settings.remove_allowed_link(self)


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

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, LinkAction) and __value.id == self.id

    def __ne__(self, __value: object) -> bool:
        return not self.__eq__(__value)

    def __hash__(self, __value: object) -> int:
        return hash(self.id)

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

        # Need to remove this action from the settings
        settings = self.settings
        if settings is None:
            return

        settings.actions.remove(self)


class ExemptTargetType(enum.Enum):
    role = 'role'
    user = 'user'
    channel = 'channel'


class ExemptTarget:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.settings_id: int = data['settings_id']
        self.exempt_id: int = data['exempt_id']
        self.exempt_type: ExemptTargetType = ExemptTargetType(data['exempt_type'])

    @classmethod
    async def create(
        cls: Type[Self], *, bot: FuryBot, connection: ConnectionType, settings_id: int, id: int, type: ExemptTargetType
    ) -> Self:
        settings = bot.get_link_setting(settings_id)
        if settings is None:
            raise ValueError('No link settings found for guild_id')

        data = await connection.fetchrow(
            'INSERT ITO links.exempt_targets (settings_id, exempt_id, exempt_type) VALUES ($1, $2, $3) RETURNING *',
        )
        assert data

        self = cls(bot=bot, data=dict(data))

        settings.add_exempt_target(self)

        return self

    @property
    def settings(self) -> Optional[LinkSettings]:
        return self.bot.get_link_setting(self.settings_id)

    @property
    def mention(self) -> str:
        if self.exempt_type is ExemptTargetType.channel:
            return f'<#{self.exempt_id}>'
        elif self.exempt_type is ExemptTargetType.role:
            return f'<@&{self.exempt_id}>'
        elif self.exempt_type is ExemptTargetType.user:
            return f'<@{self.exempt_id}>'
        else:
            raise ValueError(f'Unknown exempt type {self.exempt_type}')

    def resolve(self) -> Optional[Union[discord.Role, discord.abc.User, discord.abc.GuildChannel, discord.Thread]]:
        settings = self.settings
        if settings is None:
            return

        guild = settings.guild
        if guild is None:
            return

        if self.exempt_type is ExemptTargetType.role:
            return guild.get_role(self.exempt_id)
        elif self.exempt_type is ExemptTargetType.channel:
            return guild.get_channel_or_thread(self.exempt_id)
        elif self.exempt_type is ExemptTargetType.user:
            return guild.get_member(self.exempt_id) or self.bot.get_user(self.exempt_id)

    async def edit(
        self,
        *,
        connection: ConnectionType,
        exempt_id: int = MISSING,
        exempt_type: ExemptTargetType = MISSING,
    ) -> None:
        builder = QueryBuilder('links.exempt_targets')
        builder.add_condition('id', self.id)

        if exempt_id is not MISSING:
            builder.add_arg('exempt_id', exempt_id)
            self.exempt_id = exempt_id

        if exempt_type is not MISSING:
            builder.add_arg('exempt_type', exempt_type.value)
            self.exempt_type = exempt_type

        await builder(connection)

    async def delete(self, *, connection: ConnectionType) -> None:
        await connection.execute('DELETE FROM links.exempt_targets WHERE id = $1', self.id)

        settings = self.settings
        if settings is not None:
            settings.remove_exempt_target(self)


class LinkSettings:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.guild_id: int = data['guild_id']
        self.notifier_channel_id: Optional[int] = data['notifier_channel_id']
        self.actions: List[LinkAction] = []
        self.allowed_links: List[AllowedLink] = []
        self.exempt_targets: List[ExemptTarget] = []

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

    def add_exempt_target(self, target: ExemptTarget) -> None:
        self.exempt_targets.append(target)

    def remove_exempt_target(self, target: ExemptTarget) -> None:
        self.exempt_targets.remove(target)

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

    async def create_exempt_target(self, *, connection: ConnectionType, id: int, type: ExemptTargetType) -> ExemptTarget:
        return await ExemptTarget.create(bot=self.bot, connection=connection, settings_id=self.id, id=id, type=type)

    async def create_allowed_link(
        self, *, connection: ConnectionType, url: str, added_at: datetime.datetime, added_by_id: int
    ) -> AllowedLink:
        return await AllowedLink.create(
            bot=self.bot,
            connection=connection,
            settings_id=self.id,
            url=url,
            added_at=added_at,
            added_by_id=added_by_id,
        )

    async def delete(self, *, connection: ConnectionType) -> None:
        await connection.execute('DELETE FROM links.settings WHERE id = $1', self.id)
