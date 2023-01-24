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
import dataclasses
import datetime
import logging
from typing import TYPE_CHECKING, Any, Coroutine, Dict, List, Optional, Tuple, cast

import discord
from discord import app_commands
from discord.ext import tasks

from utils import BaseCog, Guildable, human_join
from utils.time import human_timedelta

if TYPE_CHECKING:
    from bot import FuryBot

    from ..team import Team

__all__: Tuple[str, ...] = ('PracticeLeaderboard', 'PracticeLeaderboardCog')

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


@dataclasses.dataclass(init=True, kw_only=True)
class PracticeLeaderboard(Guildable):
    """Represents a practice leaderboard for a specific guild.

    A guild can have multiple practice leaderboards, each in a different channel.

    Parameters
    Attributes
    ----------
    id: :class:`int`
        The ID of the leaderboard.
    channel_id: :class:`int`
        The ID of the channel this leaderboard is in.
    guild_id: :class:`int`
        The ID of the guild this leaderboard is in.
    message_id: :class:`int`
        The ID of the message this leaderboard is bound to. This is used to update the leaderboard.
    top_team_id: :class:`int`
        The ID of the team that is currently on top of the leaderboard.
    role_id: :class:`int`
        Th ID of the role assigned to the members of the current top team.
    bot: :class:`FuryBot`
        The bot instance.
    """

    id: int
    channel_id: int
    guild_id: int
    message_id: int
    top_team_id: int
    role_id: int
    bot: FuryBot

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    @property
    def channel(self) -> Optional[discord.TextChannel]:
        """Optional[:class:`discord.TextChannel`]: The channel this leaderboard is in."""
        guild = self.guild
        if guild is None:
            return None

        return cast(Optional[discord.TextChannel], guild.get_channel(self.channel_id))

    @property
    def role(self) -> Optional[discord.Role]:
        """Optional[:class:`discord.Role`]: The role assigned to the members of the current top team."""
        guild = self.guild
        if guild is None:
            return None

        return cast(Optional[discord.Role], guild.get_role(self.role_id))

    async def fetch_message(self) -> Optional[discord.Message]:
        """|coro|

        A helper method used to fetch the message this leaderboard is bound to.

        Returns
        -------
        Optional[:class:`discord.Message`]
            The message this leaderboard is bound to. ``None`` if the channel this leaderboard
            is in is not found.
        """
        channel = self.channel
        if channel is None:
            return None

        return await channel.fetch_message(self.message_id)

    async def change_top_team(self, team: Team) -> None:
        """|coro|

        Changes the current top team to another one and manages the roles of the members.

        Parameters
        ----------
        team: :class:`Team`
            The team to change the top team to.
        """
        role = self.role
        if role is None:
            # NOTE: Add exception raising here / auto removing leaderboard
            return

        futures: List[Coroutine[Any, Any, None]] = []

        previous_top_team = self.bot.get_team(self.top_team_id, team.guild_id)
        if previous_top_team:
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

    async def delete(self) -> None:
        """|coro|

        Delete the leaderboard from the database and the message it is bound to.
        """
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.practice_leaderboards WHERE id = $1;', self.id)

        message = await self.fetch_message()
        if message is not None:
            await message.delete()


class PracticeLeaderboardCog(BaseCog):
    practice_leaderboard = app_commands.Group(
        name='practice-leaderboard',
        description='Manage practice leaderboards.',
        guild_only=True,
        default_permissions=discord.Permissions(manage_channels=True),
    )

    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

        # mapping of {guild id: {channel id: practice_leaderboard}}
        self.leaderboard_cache: Dict[int, Dict[int, PracticeLeaderboard]] = {}

    async def cog_load(self) -> None:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM teams.practice_leaderboards;')

        for entry in data:
            self.leaderboard_cache.setdefault(entry['guild_id'], {})[entry['channel_id']] = PracticeLeaderboard(
                bot=self.bot, **dict(entry)
            )

        self.update_leaderboards.start()

    async def cog_unload(self) -> None:
        self.update_leaderboards.stop()

    @practice_leaderboard.command(name='create', description='Create a practice leaderboard.')
    @app_commands.describe(
        channel='The channel the leaderboard should be posted in.',
        role='The role to ping when a team is on top of the leaderboard.',
    )
    async def practcie_leaderboard_create(
        self, interaction: discord.Interaction, role: discord.Role, channel: Optional[discord.TextChannel]
    ) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        if channel is None:
            if not isinstance(interaction.channel, discord.TextChannel):
                return await interaction.edit_original_response(
                    content='You need to use this command in a text channel or specify a channel.',
                )

            channel = interaction.channel

        guild_leaderboards = self.leaderboard_cache.get(interaction.guild.id)
        if guild_leaderboards is not None:
            potential_leaderboard = guild_leaderboards.get(channel.id)
            if potential_leaderboard is not None:
                return await interaction.edit_original_response(
                    content="Hey! There's already a leaderboard in that channel!",
                )

        teams = self.bot.get_teams(interaction.guild.id)
        if not teams:
            return await interaction.edit_original_response(
                content='Hey! There are no teams in this server!',
            )

        embed = self.bot.Embed(
            title='Creating Practice Leaderboard',
            description='Hold tight! I\'m creating your practice leaderboard now....',
        )
        message = await channel.send(embed=embed)

        top_ten_teams = sorted(teams, key=lambda team: team.get_total_practice_time(), reverse=True)[:10]
        top_team = top_ten_teams[0]

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.practice_leaderboards(channel_id, guild_id, message_id, top_team_id, role_id) '
                'VALUES ($1, $2, $3, $4, $5) '
                'RETURNING *',
                channel.id,
                interaction.guild.id,
                message.id,
                top_team.id,
                role.id,
            )
            assert data

        leaderboard = PracticeLeaderboard(bot=self.bot, **dict(data))
        self.leaderboard_cache.setdefault(interaction.guild.id, {})[channel.id] = leaderboard

        embed = self.create_leaderboard_embed(interaction.guild, leaderboard)
        await message.edit(embed=embed)

        return await interaction.edit_original_response(
            content='Successfully created leaderboard! It automatically updates every 60 seconds.',
        )

    @practice_leaderboard.command(name='delete', description='Delete a practice leaderboard.')
    @app_commands.describe(
        channel='The channel the leaderboard should be deleted from.',
    )
    async def practcie_leaderboard_delete(
        self, interaction: discord.Interaction, channel: Optional[discord.TextChannel]
    ) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        if channel is None:
            if not isinstance(interaction.channel, discord.TextChannel):
                return await interaction.edit_original_response(
                    content='You need to use this command in a text channel or specify a channel.',
                )

            channel = interaction.channel

        existing_leaderboard = self.leaderboard_cache.get(interaction.guild.id, {}).get(channel.id)
        if existing_leaderboard is None:
            return await interaction.edit_original_response(
                content='Hey! There\'s no leaderboard in that channel!',
            )

        await existing_leaderboard.delete()
        self.leaderboard_cache[interaction.guild.id].pop(channel.id)

        return await interaction.edit_original_response(content='Successfully deleted leaderboard!')

    def create_leaderboard_embed(self, guild: discord.Guild, leaderboard: PracticeLeaderboard) -> Optional[discord.Embed]:
        teams = self.bot.get_teams(guild.id)
        if not teams:
            return None

        # we need to rank the teams by their total practice time.
        top_ten_teams = [
            t
            for t in sorted(teams, key=lambda team: team.get_total_practice_time(), reverse=True)
            if t.get_total_practice_time() > datetime.timedelta(seconds=0)
        ][:10]
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
            inline=False,
        )

        embed.add_field(
            name='Top 10 Teams',
            value='\n'.join(
                f'{count}. **{team.display_name}**, {human_timedelta(team.get_total_practice_time().total_seconds())}'
                for count, team in enumerate(top_ten_teams, start=1)
            ),
            inline=False,
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

        if up_and_coming_teams:
            sorted_teams: List[Tuple[Team, datetime.timedelta]] = sorted(
                up_and_coming_teams.items(), key=lambda item: item[1], reverse=True
            )[:10]

            embed.add_field(
                name='Up and Coming Teams',
                value='\n'.join(
                    f'{count}. **{team.display_name}**, {human_timedelta(duration.total_seconds())} in the past two days!'
                    for count, (team, duration) in enumerate(sorted_teams, start=1)
                ),
                inline=False,
            )

        return embed

    @tasks.loop(seconds=60)
    async def update_leaderboards(self) -> None:
        for guild_id, leaderboards in self.leaderboard_cache.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                _log.debug('Ignoring guild %s in update leaderboard.', guild_id)
                return None

            for leaderboard in leaderboards.values():
                # We need to get the top team for the given guild
                teams = self.bot.get_teams(guild_id)
                top_ten_teams = sorted(teams, key=lambda team: team.get_total_practice_time(), reverse=True)[:10]
                top_team = top_ten_teams[0]

                if top_team.id == leaderboard.top_team_id:
                    # Nothing to do
                    _log.debug("No change in top team for guild %s, skipping.", guild_id)
                    return

                await leaderboard.change_top_team(top_team)

                message = await leaderboard.fetch_message()
                if message is None:
                    _log.debug('Unable to fetch message from leaderboard %s, skipping.', leaderboard.id)
                    return

                embed = self.create_leaderboard_embed(guild, leaderboard)
                await message.edit(embed=embed)

                _log.debug('Updated leaderboard %s for guild %s.', leaderboard.id, guild_id)

    @update_leaderboards.before_loop
    async def before_update_leaderboards(self) -> None:
        await self.bot.wait_until_ready()
        _log.info('Starting practice leaderboard update loop.')
