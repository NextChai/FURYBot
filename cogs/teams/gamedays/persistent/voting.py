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


from typing import TYPE_CHECKING, Dict
from typing_extensions import Self

import discord
from utils import human_join, human_timestamp

if TYPE_CHECKING:
    from ..gameday import Gameday, GamedayMember
    from ...team import TeamMember
    from bot import FuryBot


class AttendanceVotingView(discord.ui.View):
    """A dynamic view that allows users to vote on attendance for a gameday."""

    def create_embed(self, gameday: Gameday) -> discord.Embed:
        team = gameday.team
        if team is None:
            raise ValueError('Gameday is missing a team.')

        embed = team.embed(
            title=f'Gameday Attendance Voting For {human_timestamp(gameday.starts_at)} gameday.',
            description=f'**Voting Started At**: {human_timestamp(gameday.voting.starts_at)}\n'
            f'**Voting Ends At**: {human_timestamp(gameday.voting.ends_at)}',
        )

        attending_members: Dict[int, GamedayMember] = {}
        not_attending_members: Dict[int, GamedayMember] = {}

        for member in gameday.members.values():
            if member.is_attending:
                attending_members[member.id] = member
            else:
                not_attending_members[member.id] = member

        waiting_on_members: Dict[int, TeamMember] = {
            team_member.member_id: team_member
            for team_member in team.members
            if team_member.member_id not in attending_members and team_member.member_id not in not_attending_members
        }

        embed.add_field(
            name='Attending Members', value=human_join((m.mention for m in attending_members.values())), inline=False
        )
        embed.add_field(
            name='Not Attending Members',
            value='\n'.join(f'{member.mention}: {member.reason}' for member in not_attending_members.values()),
            inline=False,
        )

        embed.add_field(
            name='Waiting on..', value=human_join((m.mention for m in waiting_on_members.values())), inline=False
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> bool:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message('You can only use this in a server.', ephemeral=True)
            return False

        # Let's try and find the given team from this interaction channel
        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.response.send_message('You can only use this in a team channel.', ephemeral=True)
            return False

        message_id = interaction.message and interaction.message.id
        if message_id is None:
            await interaction.response.send_message(
                'The message found on this interaction is missing, how did you do this? Contact a developer.', ephemeral=True
            )
            return False

        team = interaction.client.get_team_from_channel(channel_id, guild_id)
        if team is None:
            await interaction.response.send_message('You can only use this in a team channel.', ephemeral=True)
            return False

        team_member = team.get_member(interaction.user.id)
        if team_member is None:
            await interaction.response.send_message(
                'You are not a member of this team, you can not do this action.', ephemeral=True
            )
            return False

        bucket = team.get_gameday_bucket()
        if bucket is None:
            await interaction.response.send_message('This team has no gameday bucket, you can not use this!', ephemeral=True)
            return False

        # We need to find a gameday from this team that has a voting message ID of the message_id variable,
        # and check if voting is in progress.
        valid_gameday = discord.utils.find(
            lambda gameday: gameday.voting.message_id == message_id
            and gameday.voting.starts_at < interaction.created_at
            and gameday.voting.ends_at > interaction.created_at,
            bucket.get_gamedays(),
        )
        if valid_gameday is None:
            await interaction.response.send_message(
                'I could not find a gameday that is currently in voting on this message.', ephemeral=True
            )
            return False

        gameday_member = valid_gameday.get_member(interaction.user.id)
        if gameday_member is not None:
            await interaction.response.send_message(
                'You are already a member of this gameday, you can not vote on this.', ephemeral=True
            )
            return False

        return True

    def _get_current_gameday(self, interaction: discord.Interaction[FuryBot]) -> Gameday:
        assert interaction.guild_id
        assert interaction.channel_id

        team = interaction.client.get_team_from_channel(interaction.channel_id, interaction.guild_id)
        assert team

        bucket = team.get_gameday_bucket()
        assert bucket

        message_id = interaction.message and interaction.message.id
        assert message_id

        valid_gameday = discord.utils.find(
            lambda gameday: gameday.voting.message_id == message_id
            and gameday.voting.starts_at < interaction.created_at
            and gameday.voting.ends_at > interaction.created_at,
            bucket.get_gamedays(),
        )
        assert valid_gameday

        return valid_gameday

    @discord.ui.button(label='I Can Attend', style=discord.ButtonStyle.green)
    async def attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = self._get_current_gameday(interaction)

    @discord.ui.button(label='I Can Not Attend', style=discord.ButtonStyle.red)
    async def not_attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = self._get_current_gameday(interaction)
