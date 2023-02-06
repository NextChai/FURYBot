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

import logging
from typing import TYPE_CHECKING, Tuple, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog

from ..team import Team
from ..errors import MemberNotOnTeam
from .errors import *
from .leaderboard import *
from .persistent import *
from .practice import *

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('PracticeCog',)

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class PracticeCog(PracticeLeaderboardCog, BaseCog):
    """Represents the main practice cog. This cog manages the creation of practices, as well
    as the creation of the practice leaderboard.

    The practice leaderboard commands are found in the :class:`.PracticeLeaderboardCog` class
    that this class inherits from.
    """

    practice = app_commands.Group(
        name='practice',
        description='Manage and start practices.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @practice.command(name='start', description='Start a practice for your team.')
    async def practice_start(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|

        Start a new practice within a team channel. This command can only be used in a team channel by a member
        on a team.
        """
        assert interaction.guild

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
            team = Team.from_channel(category.id, interaction.guild.id, bot=self.bot)
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

        embed = team.embed(
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
                PracticeStatus.ongoing.value,
                interaction.user.id,
                message.id,
            )
            assert practice_data

            practice = Practice(bot=self.bot, data=dict(practice_data))

            # Add this practice to the bot so we can access it later
            self.bot.add_practice(practice)
            
        # Add all members in the voice channel already
        for connected_member in connected_channel.members:
            try:
                await practice.handle_member_join(member=connected_member, when=interaction.created_at)
            except MemberNotOnTeam:
                pass

        await interaction.edit_original_response(content="A new practice has been created.")

    @commands.Cog.listener('on_voice_state_update')
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> Optional[PracticeMember]:
        """|coro|

        A listener to keep track of when members join and leave a practice.

        Parameters
        ---------
        member: :class:`discord.Member`
            The member that joined or left a voice channel.
        before: :class:`discord.VoiceState`
            The voice state before the member joined or left a voice channel.
        after: :class:`discord.VoiceState`
            The voice state after the member joined or left a voice channel.
        """
        if before.channel == after.channel:
            # The two channels are the same, return
            return

        if not before.channel and after.channel:
            _log.debug('Member %s joined a voice channel.', member.id)

            category = after.channel.category
            if not category:
                _log.debug('Member %s joined a voice channel that is not in a category.', member.id)
                return

            try:
                team = Team.from_channel(category.id, member.guild.id, bot=self.bot)
            except Exception:
                _log.debug('Member %s joined a voice channel that is not in a team channel.', member.id)
                return

            # Make sure the member joined the team's voice channel
            if after.channel != team.voice_channel:
                _log.debug('Member %s joined a voice channel that is not the team\'s voice channel.', member.id)
                return

            practice = team.ongoing_practice
            if not practice:
                _log.debug('Member %s joined a voice channel that is not in an ongoing practice.', member.id)
                return

            try:
                return await practice.handle_member_join(member=member)
            except (MemberNotOnTeam, MemberNotAttendingPractice):
                return

        elif before.channel and not after.channel:
            _log.debug('Member %s left a voice channel.', member.id)

            category = before.channel.category
            if not category:
                _log.debug('Member %s left a voice channel that is not in a category.', member.id)
                return

            try:
                team = Team.from_channel(category.id, member.guild.id, bot=self.bot)
            except Exception:
                _log.debug('Member %s left a voice channel that is not in a team channel.', member.id)
                return

            if before.channel != team.voice_channel:
                _log.debug('Member %s left a voice channel that is not the team\'s voice channel.', member.id)
                return

            practice = team.ongoing_practice
            if not practice:
                _log.debug('Member %s left a voice channel that is not in an ongoing practice.', member.id)
                return

            try:
                return await practice.handle_member_leave(member=member)
            except (MemberNotOnTeam, MemberNotInPractice, MemberNotAttendingPractice):
                return

        elif before.channel and after.channel:  # Member switched voice channels
            # When a member switches voice channels, they can technically hop from one practice
            # to another. To account for this, we need to check in this methodology.

            # 1. Check if the member's old category is a team category. If it is, handle removing them from the practice.
            # 2. Check if the member's new category is a team category. If it is, handle adding them to the practice.

            before_category = before.channel.category
            if before_category:
                # Check if the before category is a team category
                try:
                    team = Team.from_channel(before_category.id, member.guild.id, bot=self.bot)
                except Exception:
                    pass
                else:
                    # We found a team, make sure the member was in the team's voice channel
                    if before.channel == team.voice_channel:
                        # Check if the team has an ongoing practice
                        practice = team.ongoing_practice
                        if practice:
                            try:
                                await practice.handle_member_leave(member=member)
                            except (MemberNotOnTeam, MemberNotInPractice, MemberNotAttendingPractice):
                                pass
        
            after_category = after.channel.category
            if after_category:
                # Check if this new category is a team category
                try:
                    team = Team.from_channel(after_category.id, member.guild.id, bot=self.bot)
                except Exception:
                    pass
                else:
                    # We found a team, make sure the member joined the team's voice channel
                    if after.channel == team.voice_channel:
                        # Check if the team has an ongoing practice
                        practice = team.ongoing_practice
                        if practice:
                            try:
                                await practice.handle_member_join(member=member)
                            except (MemberNotOnTeam, MemberNotAttendingPractice):
                                pass

async def setup(bot: FuryBot) -> None:
    await bot.add_cog(PracticeCog(bot))
