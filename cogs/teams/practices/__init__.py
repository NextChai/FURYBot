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

from .errors import *
from .persistent import *
from .practice import *

from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord import app_commands

from utils import BaseCog
from ..team import Team

if TYPE_CHECKING:
    from bot import FuryBot


class PracticeCog(BaseCog):

    practice = app_commands.Group(
        name='practice',
        description='Manage and start practices.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @practice.command(name='start', description='Start a practice for your team.')
    async def practice_start(self, interaction: discord.Interaction[FuryBot]) -> None:
        # Let's check to make sure this is a team channel first.
        channel = interaction.channel
        assert channel

        member = interaction.user
        assert isinstance(member, discord.Member)

        category = getattr(channel, 'category', None)
        if category is None:
            return await interaction.response.send_message('You must use this command in a team channel.', ephemeral=True)

        # Let's try and get a team now
        try:
            team = Team.from_category(category.id, bot=self.bot)
        except Exception:
            return await interaction.response.send_message('You must use this command in a team channel.', ephemeral=True)

        # Let's check and see if there's an active practice
        if team.ongoing_practice is not None:
            return await interaction.response.send_message(
                'There is already an active practice for this team.', ephemeral=True
            )

        # Now we can verify they're in the team's voice channel
        connected_channel = member.voice and member.voice.channel
        if not connected_channel or connected_channel != team.voice_channel:
            return await interaction.response.send_message(
                'You must be in the team\'s voice channel to start a practice.', ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        embed = self.bot.Embed(
            title="Creating Practice...",
            description="Please wait while we create your practice.",
        )
        message = await team.text_channel.send(embed=embed)

        # We can create a new practice now.
        async with self.bot.safe_connection() as connection:
            practice_data = await connection.fetchrow(
                """INSERT INTO teams.practice(
                    started_at, team_id, channel_id, guild_id, status, started_by_id, message_id
                ) VALUES(
                    $1, $2, $3, $4, $5, $6, $7
                ) RETURNING *
                """,
                interaction.created_at,
                team.id,
                connected_channel.id,
                connected_channel.guild.id,
                PracticeStatus.ongoing,
                interaction.user.id,
                message.id,
            )
            assert practice_data

        practice = Practice(bot=self.bot, data=dict(practice_data))

        await practice.handle_member_join(member=member, when=interaction.created_at)
        await interaction.edit_original_response(content="A new practice has been created.")

    @commands.Cog.listener('on_voice_state_update')
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> Optional[PracticeMember]:
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            # The member joined a voice channel
            joined_channel = after.channel
            category: Optional[discord.CategoryChannel] = joined_channel.category

            if category is None:
                return

            try:
                team = Team.from_category(category.id, bot=self.bot)
            except Exception:
                return

            # Check if this team has an ongoing practice
            practice = team.ongoing_practice
            if practice is None:
                return

            # This member joined an ongoing practice.
            try:
                return await practice.handle_member_join(member=member)
            except MemberNotOnTeam:
                return

        elif before.channel is not None and after.channel is None:  # The member left a voice channel.
            left_chanenl = before.channel
            category: Optional[discord.CategoryChannel] = left_chanenl.category

            if category is None:
                return

            try:
                team = Team.from_category(category.id, bot=self.bot)
            except Exception:
                return

            # Check if there's an ongoing practice
            practice = team.ongoing_practice
            if practice is None:
                return

            try:
                return await practice.handle_member_leave(member=member)
            except (MemberNotOnTeam, MemberNotInPractice):
                return


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(PracticeCog(bot))
