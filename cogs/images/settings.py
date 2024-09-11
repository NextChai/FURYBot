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
from typing import TYPE_CHECKING, Any, Dict, Optional, Type
from typing_extensions import Self
import discord

from utils import QueryBuilder

if TYPE_CHECKING:
    from bot import FuryBot

MISSING = discord.utils.MISSING


class AttachmentRequestSettings:
    def __init__(self, *, data: Dict[str, Any], bot: FuryBot) -> None:
        self.bot: FuryBot = bot

        self.id: int = data['id']
        self.channel_id: int = data['channel_id']  # The channel to send the attachments to
        self.guild_id: int = data['guild_id']  # The guild to send the attachments to
        self.notification_role_id: Optional[int] = data.get(
            'notification_role_id'
        )  # The role to ping when a new attachment is sent

    @classmethod
    async def create(
        cls: Type[Self],
        guild_id: int,
        channel_id: int,
        /,
        *,
        bot: FuryBot,
        notification_role_id: Optional[int] = None,
    ) -> Self:
        async with bot.safe_connection() as connection:
            async with connection.transaction():
                record = await connection.fetchrow(
                    '''
                    INSERT INTO images.request_settings (guild_id, channel_id, notification_role_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET channel_id = EXCLUDED.channel_id, notification_role_id = EXCLUDED.notification_role_id
                    RETURNING *
                    ''',
                    guild_id,
                    channel_id,
                    notification_role_id,
                )
                assert record is not None

        return cls(data=dict(record), bot=bot)

    @classmethod
    async def fetch_from_guild(cls: Type[Self], guild_id: int, /, *, bot: FuryBot) -> Optional[Self]:
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM images.request_settings WHERE guild_id = $1', guild_id)

        if not data:
            return None

        return cls(data=dict(data), bot=bot)

    @classmethod
    async def fetch_from_id(cls: Type[Self], id: int, /, *, bot: FuryBot) -> Optional[Self]:
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM images.request_settings WHERE id = $1', id)

        if not data:
            return None

        return cls(data=dict(data), bot=bot)

    @property
    def channel(self) -> Optional[discord.TextChannel]:
        guild = self.guild
        if not guild:
            return None

        channel = guild.get_channel(self.channel_id)
        if not channel:
            return None

        assert isinstance(channel, discord.TextChannel)
        return channel

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def notification_role(self) -> Optional[discord.Role]:
        if not self.notification_role_id:
            return None

        guild = self.guild
        if not guild:
            return None

        return guild.get_role(self.notification_role_id)

    async def edit(
        self,
        *,
        channel_id: int = MISSING,
        notification_role_id: Optional[int] = MISSING,
    ) -> None:
        builder = QueryBuilder('images.request_settings')
        builder.add_condition('id', self.id)

        if channel_id is not MISSING:
            self.channel_id = channel_id
            builder.add_arg('channel_id', channel_id)

        if notification_role_id is not MISSING:
            self.notification_role_id = notification_role_id
            builder.add_arg('notification_role_id', notification_role_id)

        async with self.bot.safe_connection() as connection:
            await builder(connection)

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM images.request_settings WHERE id = $1', self.id)
