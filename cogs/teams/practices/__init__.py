"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to 
non-commercial purposes. Distribution, sublicensing, and sharing of this file 
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not 
misrepresent the original material. This license does not grant any 
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog

from ..errors import MemberNotOnTeam, TeamNotFound
from ..team import Team

# for imports and ease of use for other modules
from .errors import *  # noqa
from .leaderboard import *  # noqa
from .persistent import *  # noqa
from .practice import *  # noqa

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ("PracticeCog",)

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class PracticeCog(PracticeLeaderboardCog, BaseCog):
    """Represents the main practice cog. This cog manages the creation of practices, as well
    as the creation of the practice leaderboard.

    The practice leaderboard commands are found in the :class:`.PracticeLeaderboardCog` class
    that this class inherits from.
    """

    practice = app_commands.Group(
        name="practice",
        description="Manage and start practices.",
        guild_only=True,
    )

    @staticmethod
    async def _fetch_current_voice_channel(
        interaction: discord.Interaction[FuryBot], team: Team, target: discord.Member
    ) -> Optional[Union[discord.VoiceChannel, discord.StageChannel]]:
        """Determines if a scrim can start and fetches the active voice channel of the user.
        If failed, will let the user know and return None. Else, returns the voice channel.

        """
        # Let's check and see if there's an active practice
        if team.ongoing_practice is not None:
            return await interaction.followup.send("There is already an active practice for this team.", ephemeral=True)

        # If this team does not have a voice channel, they are physically unable to do
        # a practice.
        if team.voice_channel is None:
            return await interaction.followup.send(
                "This team does not have a voice channel. Please contact an administrator to get one.",
                ephemeral=True,
            )

        # If this team doesn't have a text channel either they cannot do a practice
        team_text_channel = team.text_channel
        if team_text_channel is None:
            return await interaction.followup.send(
                "This team does not have a main text channel. Was it deleted? Why? Please contact an administrator to get one.",
                ephemeral=True,
            )

        # Now we can verify they're in the team's voice channel
        connected_channel = target.voice and target.voice.channel
        if not connected_channel or connected_channel != team.voice_channel:
            return await interaction.followup.send(
                "You must be in the team's voice channel to start a practice.",
                ephemeral=True,
            )

        return connected_channel

    async def _create_practice(
        self,
        interaction: discord.Interaction[FuryBot],
        team: Team,
        member: discord.Member,
        connected_channel: Union[discord.VoiceChannel, discord.StageChannel],
        message: discord.Message,
    ) -> Practice:
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
            if not practice_data:
                raise ValueError("Failed to create a practice.")

            practice = Practice(bot=self.bot, data=dict(practice_data))

            # Add this practice to the bot so we can access it later
            self.bot.add_practice(practice)

        await practice.handle_member_join(member=member, when=interaction.created_at)

        # Add all members in the voice channel already
        for connected_member in connected_channel.members:
            if connected_member == member:
                continue

            try:
                await practice.handle_member_join(member=connected_member, when=interaction.created_at)
            except MemberNotOnTeam:
                pass

        return practice

    @practice.command(name="start", description="Start a practice for your team.")
    async def practice_start(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|

        Start a new practice within a team channel. This command can only be used in a team channel by a member
        on a team.
        """
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            raise ValueError('Invariant that guild invoke has failed.')

        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.followup.send("You must be a in a server to use this command.", ephemeral=True)

        category = interaction.channel and getattr(interaction.channel, "category", None)
        if category is None:
            return await interaction.followup.send("You must use this command in a team channel.", ephemeral=True)

        # Let's try and get a team now
        try:
            team = Team.from_channel(category.id, interaction.guild.id, bot=self.bot)
        except TeamNotFound:
            return await interaction.followup.send("You must use this command in a team channel.", ephemeral=True)

        connected_channel = await self._fetch_current_voice_channel(interaction, team, member)
        if not connected_channel:
            # This is an invalid practice start, return
            return

        # We know from _fetch_current_voice_channel that the team text channel exists, so we can safely
        # get it here.
        team_text_channel = team.text_channel
        if not team_text_channel:
            raise ValueError("Team text channel does not exist, this should never happen.")

        embed = team.embed(
            title="Creating Practice...",
            description="Please wait while we create your practice.",
        )
        message = await team_text_channel.send(embed=embed)

        await self._create_practice(
            interaction=interaction,
            team=team,
            member=member,
            connected_channel=connected_channel,
            message=message,
        )

        await interaction.followup.send(content="A new practice has been created.", ephemeral=True)

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
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
            _log.debug("Member %s joined a voice channel.", member.id)

            category = after.channel.category
            if not category:
                _log.debug(
                    "Member %s joined a voice channel that is not in a category.",
                    member.id,
                )
                return

            try:
                team = Team.from_channel(category.id, member.guild.id, bot=self.bot)
            except TeamNotFound:
                _log.debug(
                    "Member %s joined a voice channel that is not in a team channel.",
                    member.id,
                )
                return

            # Make sure the member joined the team's voice channel
            if after.channel != team.voice_channel:
                _log.debug(
                    "Member %s joined a voice channel that is not the team's voice channel.",
                    member.id,
                )
                return

            practice = team.ongoing_practice
            if not practice:
                _log.debug(
                    "Member %s joined a voice channel that is not in an ongoing practice.",
                    member.id,
                )
                return

            try:
                return await practice.handle_member_join(member=member)
            except (MemberNotOnTeam, MemberNotAttendingPractice):
                return

        elif before.channel and not after.channel:
            _log.debug("Member %s left a voice channel.", member.id)

            category = before.channel.category
            if not category:
                _log.debug(
                    "Member %s left a voice channel that is not in a category.",
                    member.id,
                )
                return

            try:
                team = Team.from_channel(category.id, member.guild.id, bot=self.bot)
            except TeamNotFound:
                _log.debug(
                    "Member %s left a voice channel that is not in a team channel.",
                    member.id,
                )
                return

            if before.channel != team.voice_channel:
                _log.debug(
                    "Member %s left a voice channel that is not the team's voice channel.",
                    member.id,
                )
                return

            practice = team.ongoing_practice
            if not practice:
                _log.debug(
                    "Member %s left a voice channel that is not in an ongoing practice.",
                    member.id,
                )
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
                except TeamNotFound:
                    pass
                else:
                    # We found a team, make sure the member was in the team's voice channel
                    if before.channel == team.voice_channel:
                        # Check if the team has an ongoing practice
                        practice = team.ongoing_practice
                        if practice:
                            try:
                                await practice.handle_member_leave(member=member)
                            except (
                                MemberNotOnTeam,
                                MemberNotInPractice,
                                MemberNotAttendingPractice,
                            ):
                                pass

            after_category = after.channel.category
            if after_category:
                # Check if this new category is a team category
                try:
                    team = Team.from_channel(after_category.id, member.guild.id, bot=self.bot)
                except TeamNotFound:
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
