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

import logging
from typing import TYPE_CHECKING, Dict, Optional, cast

import discord
from discord import app_commands
from discord.ext import tasks

from utils import BaseCog, Guildable

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from bot import FuryBot
    from ..team import Team


@dataclasses.dataclass(init=True, kw_only=True)
class PracticeLeaderboard(Guildable):
    id: int
    channel_id: int
    guild_id: int
    message_id: int
    top_team_id: Optional[int]
    role_id: int
    bot: FuryBot

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    @property
    def channel(self) -> Optional[discord.TextChannel]:
        guild = self.guild
        if guild is None:
            return None

        return cast(Optional[discord.TextChannel], guild.get_channel(self.channel_id))

    @property
    def role(self) -> Optional[discord.Role]:
        guild = self.guild
        if guild is None:
            return None

        return cast(Optional[discord.Role], guild.get_role(self.role_id))

    async def fetch_message(self) -> Optional[discord.Message]:
        channel = self.channel
        if channel is None:
            return None

        return await channel.fetch_message(self.message_id)

    async def update_top_team(self, team: Team) -> None:
        self.top_team_id = team.id
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.practice_leaderboards SET top_team_id = $1 WHERE id = $2;',
                team.id,
                self.id,
            )


class PracticeLeaderboardCog(BaseCog):
    practice_leaderboard = app_commands.Group(
        name='practice-leaderboard',
        description='Manage practice leaderboards.',
        guild_only=True,
        default_permissions=discord.Permissions(manage_channels=True),
    )

    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

        # mapping of {guild id: {practice leaderboard id: practice_leaderboard}}
        self.leaderboard_cache: Dict[int, Dict[int, PracticeLeaderboard]] = {}

    async def cog_load(self) -> None:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM teams.practice_leaderboards;')

        for entry in data:
            self.leaderboard_cache.setdefault(entry['guild_id'], {})[entry['id']] = PracticeLeaderboard(
                bot=self.bot, **dict(entry)
            )

        self.update_leaderboards.start()

    async def cog_unload(self) -> None:
        self.update_leaderboards.stop()

    @practice_leaderboard.command(name='create', description='Create a practice leaderboard in a new channel.')
    async def practice_leaderboard_create(
        self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role
    ) -> None:
        assert interaction.guild is not None

        current_leaderboards = self.leaderboard_cache.get(interaction.guild.id, [])
        if channel.id in current_leaderboards:
            return await interaction.response.send_message('This channel is already a practice leaderboard.', ephemeral=True)

        embed = self.create_leaderboard_embed(interaction.guild)
        if embed is None:
            return await interaction.response.send_message('There are no teams in this server.', ephemeral=True)

        message = await channel.send(embed=embed)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'INSERT INTO teams.practice_leaderboards (guild_id, channel_id, message_id, role_id) VALUES ($1, $2, $3, $4);',
                interaction.guild.id,
                channel.id,
                message.id,
                role.id,
            )

    def create_leaderboard_embed(self, guild: discord.Guild) -> Optional[discord.Embed]:
        teams = [team for team in self.bot.team_cache.values() if team.guild == guild]
        if not teams:
            return None

        # we need to rank the teams by their total practice time.
        top_ten_teams = sorted(teams, key=lambda team: team.get_total_practice_time(), reverse=True)[:10]
        top_team = top_ten_teams[0]

        embed = top_team.embed(
            title="Practice Leaderboard",
            description="Below represents the practice leaderboard for the teams on this server! "
            f"This is a cumulative report based on the practice times logged from {self.bot.user.mention}. "
            "To increase your team's practice time, start a Fury Bot practice with your team and play together!",
        )

    @tasks.loop(seconds=60)
    async def update_leaderboards(self) -> None:
        ...

    @update_leaderboards.before_loop
    async def before_update_leaderboards(self) -> None:
        await self.bot.wait_until_ready()
        _log.info('Starting practice leaderboard update loop.')
