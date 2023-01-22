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
import dataclasses

import logging
from typing import TYPE_CHECKING, Any, Coroutine, Dict, Optional, cast, List, Tuple

import discord
from discord import app_commands
from discord.ext import tasks

from utils import BaseCog, Guildable, human_join
from utils.time import human_timedelta

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

    async def change_top_team(self, team: Team) -> None:
        role = self.role
        if role is None:
            # NOTE: Add exception raising here / auto removing leaderboard
            return

        futures: List[Coroutine[Any, Any, None]] = []
        if self.top_team_id:
            previous_top_team = self.bot.team_cache[self.top_team_id]
            for team_member in previous_top_team.members:
                member = team_member.member or await team_member.fetch_member()
                futures.append(member.remove_roles(role, reason='Team member booted off leaderboard.'))

        self.top_team_id = team.id
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.practice_leaderboards SET top_team_id = $1 WHERE id = $2;',
                team.id,
                self.id,
            )

        # Add roles onto new team
        for team_member in team.members:
            member = team_member.member or await team_member.fetch_member()
            futures.append(member.add_roles(role, reason='Team member booted off leaderboard.'))

        await asyncio.gather(*futures)


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

    def create_leaderboard_embed(self, guild: discord.Guild, leaderboard: PracticeLeaderboard) -> Optional[discord.Embed]:
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

        member_mentions = human_join((member.mention for member in top_team.members))
        embed.add_field(
            name='Top Team',
            value=f'{member_mentions}, great work! For your efforts, you\'ve been rewarded with the '
            f'<@&{leaderboard.role_id}> role! This role will be reassigned if your team loses the #1 spot, so hold on tight!',
        )

        embed.add_field(
            name='Top 10 Teams',
            value='\n'.join(
                f'{count}. **{team.display_name}**, {human_timedelta(team.get_total_practice_time().total_seconds())}'
                for count, team in enumerate(top_ten_teams, start=1)
            ),
        )

        # We need to get the up and coming teams. These are the teams that have the most amount of pracice time
        # within the past 48 hours.
        up_and_coming_teams: Dict[Team, datetime.timedelta] = {}
        for team in teams:
            for practice in team.practices:
                duration = practice.duration
                if not duration:
                    continue

                # Check if the practice ended within the past 48 hours.
                assert practice.ended_at
                if practice.ended_at < discord.utils.utcnow() - datetime.timedelta(days=2):
                    continue

                up_and_coming_teams[team] = up_and_coming_teams.get(team, datetime.timedelta()) + duration

        sorted_teams: List[Tuple[Team, datetime.timedelta]] = sorted(
            up_and_coming_teams.items(), key=lambda item: item[1], reverse=True
        )[:10]

        embed.add_field(
            name='Up and Coming Teams',
            value='\n'.join(
                f'{count}. **{team.display_name}**, {human_timedelta(duration.total_seconds())} in the past two days!'
                for count, (team, duration) in enumerate(sorted_teams, start=1)
            ),
        )

        return embed

    @tasks.loop(seconds=60)
    async def update_leaderboards(self) -> None:
        for guild_id, leaderboards in self.leaderboard_cache.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return None

            for leaderboard in leaderboards.values():
                # We need to get the top team for the given guild
                teams = [team for team in self.bot.team_cache.values() if team.guild == guild]
                top_ten_teams = sorted(teams, key=lambda team: team.get_total_practice_time(), reverse=True)[:10]
                top_team = top_ten_teams[0]

                if top_team.id == leaderboard.top_team_id:
                    # Nothing to do
                    return

                await leaderboard.change_top_team(top_team)

                message = await leaderboard.fetch_message()
                if message is None:
                    return

                embed = self.create_leaderboard_embed(guild, leaderboard)
                await message.edit(embed=embed)

    @update_leaderboards.before_loop
    async def before_update_leaderboards(self) -> None:
        await self.bot.wait_until_ready()
        _log.info('Starting practice leaderboard update loop.')
