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

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, Union

import discord
from typing_extensions import Self

from utils import QueryBuilder

if TYPE_CHECKING:
    from bot import FuryBot

MISSING = discord.utils.MISSING


class PreviousPartialInfraction:

    def __init__(self, *, data: Dict[str, Any], settings: InfractionsSettings) -> None:
        self.guild_id: int = data['guild_id']
        self.user_id: int = data['user_id']
        self.message_id: int = data['message_id']
        self.channel_id: int = data['channel_id']
        self.settings: InfractionsSettings = settings

    @property
    def url(self) -> str:
        return f'https://discord.com/channels/{self.settings.guild_id}/{self.channel_id}/{self.message_id}'


class InfractionsSettings:
    def __init__(self, *, data: Dict[str, Any], bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.guild_id: int = data['guild_id']
        self.notification_channel_id: Optional[int] = data['notification_channel_id']
        self.moderator_ids: List[int] = data['moderators'] or []  # List of user iDS
        self.moderator_role_ids: List[int] = data['moderator_roles'] or []  # List of role IDs
        self.enable_no_dms_open: bool = data['enable_no_dms_open']
        self.enable_infraction_counter: bool = data['enable_infraction_counter']

    @classmethod
    async def create(cls: Type[Self], guild_id: int, /, *, bot: FuryBot) -> Self:
        async with bot.safe_connection() as connection:
            async with connection.transaction():
                record = await connection.fetchrow(
                    '''
                    INSERT INTO infractions.settings (guild_id)
                    VALUES ($1)
                    ON CONFLICT (guild_id) 
                    DO NOTHING
                    ''',
                    guild_id,
                )
                assert record is not None

        instance = cls(data=dict(record), bot=bot)
        bot.add_infractions_settings(instance)
        return instance

    @property
    def notification_channel(self) -> Optional[discord.TextChannel]:
        if not self.notification_channel_id:
            return None

        guild = self.guild
        if not guild:
            return None

        channel = guild.get_channel(self.notification_channel_id)
        if not channel:
            return None

        assert isinstance(channel, discord.TextChannel)
        return channel

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def moderator_roles(self) -> List[discord.Role]:
        guild = self.guild
        if not guild:
            return []

        roles: List[discord.Role] = []
        for role_id in self.moderator_role_ids:
            role = guild.get_role(role_id)
            if role:
                roles.append(role)

        return roles

    @property
    def moderators_cached(self) -> List[Union[discord.Member, discord.User]]:
        guild = self.guild
        if not guild:
            return []

        members: List[Union[discord.Member, discord.User]] = []
        for member_id in self.moderator_ids:
            member = guild.get_member(member_id)
            if not member:
                member = self.bot.get_user(member_id)

            if member:
                members.append(member)

        return members

    async def moderators(self) -> List[discord.Member]:
        guild = self.guild
        if not guild:
            return []

        members: List[discord.Member] = []
        for member_id in self.moderator_ids:
            try:
                member = guild.get_member(member_id) or await guild.fetch_member(member_id)
            except discord.NotFound:
                # This member no longer exists
                new_moderator_ids = self.moderator_ids.copy()
                new_moderator_ids.remove(member_id)
                await self.edit(moderator_ids=new_moderator_ids)
                continue

            if member:
                members.append(member)

        return members

    async def edit(
        self,
        *,
        notification_channel_id: int = MISSING,
        moderator_ids: List[int] = MISSING,
        moderator_role_ids: List[int] = MISSING,
        enable_no_dms_open: bool = MISSING,
        enable_infraction_counter: bool = MISSING,
    ) -> None:
        builder = QueryBuilder('infractions.settings')
        builder.add_condition('guild_id', self.guild_id)

        if notification_channel_id is not MISSING:
            self.notification_channel_id = notification_channel_id
            builder.add_arg('notification_channel_id', notification_channel_id)

        if moderator_ids is not MISSING:
            self.moderator_ids = moderator_ids
            builder.add_arg('moderators', moderator_ids)

        if moderator_role_ids is not MISSING:
            self.moderator_role_ids = moderator_role_ids
            builder.add_arg('moderator_roles', moderator_role_ids)

        if enable_no_dms_open is not MISSING:
            self.enable_no_dms_open = enable_no_dms_open
            builder.add_arg('enable_no_dms_open', enable_no_dms_open)

        if enable_infraction_counter is not MISSING:
            self.enable_infraction_counter = enable_infraction_counter
            builder.add_arg('enable_infraction_counter', enable_infraction_counter)

        async with self.bot.safe_connection() as connection:
            await builder(connection)

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM infractions.settings WHERE guild_id = $1', self.guild_id)

        self.bot.remove_infractions_settings(self.guild_id)

    async def fetch_infractions_count_from(self, user_id: int, /) -> int:
        async with self.bot.safe_connection() as connection:
            count = await connection.fetchval(
                '''
                SELECT COUNT(*) as count 
                FROM infractions.member_counter 
                WHERE guild_id = $1 AND user_id = $2
                ''',
                self.guild_id,
                user_id,
            )

            if count is None:
                return 0

            return count

    async def add_infraction_for(self, user_id: int, /, *, in_channel: int, message_id: int) -> None:
        if not self.notification_channel_id:
            # We cannot do anything without a notification channel
            # TODO: Maybe some sort of error?
            return

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                INSERT INTO infractions.member_counter(guild_id, user_id, message_id, channel_id)
                VALUES ($1, $2, $3, $4)
                ''',
                self.guild_id,
                user_id,
                message_id,
                in_channel,
            )

    async def fetch_most_recent_infraction_from(self, user_id: int) -> Optional[PreviousPartialInfraction]:
        async with self.bot.safe_connection() as connection:
            record = await connection.fetchrow(
                '''
                SELECT message_id, channel_id
                FROM infractions.member_counter
                WHERE guild_id = $1 AND user_id = $2
                ORDER BY message_id DESC
                LIMIT 1
                ''',
                self.guild_id,
                user_id,
            )
            if not record:
                return None

            return PreviousPartialInfraction(data=dict(record), settings=self)
