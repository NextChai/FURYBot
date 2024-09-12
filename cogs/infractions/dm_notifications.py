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
from typing import TYPE_CHECKING, List, Optional, cast

import discord
from discord.ext import tasks
from utils import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot


class DmNotifications(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.member_notifier_task.start()

    async def _fetch_and_send_members(self, guild: discord.Guild, moderators: List[int]) -> List[discord.Member]:
        embed = self.bot.Embed(
            title='Dms are on!',
            description=f'Your DM\'s are not turned off in the {guild.name} server. Please '
            'do this or one of the coaches will be reaching out to you soon.',
        )

        members: List[discord.Member] = []
        async for member in guild.fetch_members(limit=None):
            if (member.id in moderators) or member.bot:
                continue

            try:
                await member.send(embed=embed)
            except discord.HTTPException:
                pass
            else:
                members.append(member)

        return members

    async def _wrap_guild_member_sending(self, guild: discord.Guild):
        async with self.bot.safe_connection() as connection: 
            data = await connection.fetchrow(
                'SELECT notification_channel_id, moderators, moderator_role_ids FROM infractions.settings WHERE guild_id = $1',
                guild.id,
            )

        if not data:
            # Between creating the task and now, the guild was removed from the database.
            # We'll just return
            return

        moderators: List[int] = data['moderators'] or []
        if data['moderator_role_ids']:
            for role_id in data['moderator_role_ids']:
                role = guild.get_role(role_id)
                if role:
                    moderators.extend([m.id for m in role.members])

        members = await self._fetch_and_send_members(guild, moderators)
        if not members:
            return

        if not data['notification_channel_id']:
            return

        channel = cast(Optional[discord.TextChannel], guild.get_channel(data['notification_channel_id']))
        if not channel:
            return

        member_mentions: List[str] = []
        mutual_member_mentions: List[str] = []
        for member in members:
            if len(member.mutual_guilds) > 1:
                # There is a good chance that this member is in more than 1 server with this bot,
                # we'll let the staff know of this.
                guild_names = ', '.join(mg.name for mg in member.mutual_guilds if mg != guild)
                mutual_member_mentions.append(f'{member.mention} (`{member.id}`): {guild_names}')
            else:
                member_mentions.append(f'{member.mention} (`{member.id}`)')

        embed = self.bot.Embed(
            title='Members Have Dms Turned On',
            description=f'The members below have their DMs turned on.\n\n{member_mentions}',
        )

        if mutual_member_mentions:
            embed.add_field(name='Mutual Guild Enabled Dms', value='\n'.join(mutual_member_mentions))
            embed.set_footer(
                text='"Mutual guild enabled dms" are the members who share more than one server '
                'with the bot and have their DMs turned on in at least one of the servers. This may '
                'not mean that they have DMs turned on in this server.'
            )

        await channel.send(embed=embed)

    @tasks.loop(hours=3)
    async def member_notifier_task(self) -> None:
        async with self.bot.safe_connection() as connection:
            guild_id_records = await connection.fetch(
                'SELECT guild_id FROM infractions.settings WHERE notification_channel_id IS NOT NULL AND enable_no_dms_open = TRUE'
            )

            for record in guild_id_records:
                guild_id = record['guild_id']
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    await connection.execute(
                        'UPDATE infractions.settings SET notification_channel_id = NULL WHERE guild_id = $1',
                        guild_id,
                    )
                    continue

                self.bot.create_task(self._wrap_guild_member_sending(guild), name=f'notifier-{guild_id}')

                await self._wrap_guild_member_sending(guild)

    @member_notifier_task.before_loop
    async def member_notifier_before_loop(self) -> None:
        await self.bot.wait_until_ready()
