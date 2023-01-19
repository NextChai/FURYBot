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

from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog

from .practice import *
from .checks import *
from .persistent import *
from ..team import Team

if TYPE_CHECKING:
    from bot import FuryBot


class TeamPractices(BaseCog):
    """The cog for managing team practices. When a team has their practice session on
    Mondays (or their specified team time), attending members will be required to mark
    they they've attended to the practices.

    This will allow coaches to keep track of who is and isn't showing up, and subsequently make
    decisions based upon that.
    """

    practice = app_commands.Group(
        name='practice',
        description='Start a team practice.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @practice.command(name='start', description='Start a team practice.')
    @app_commands.guild_only()
    async def practice_start(self, interaction: discord.Interaction[FuryBot]) -> Optional[discord.InteractionMessage]:
        await interaction.response.defer(ephemeral=True)

        # We're going to run check ourselves, since we don't want to raise an error
        if not await is_invoked_in_team_chat(interaction):
            return await interaction.edit_original_response(content="You can only start a practice in a team channel.")

        if not await invoker_on_team(interaction):
            return await interaction.edit_original_response(content="You can only start a practice if you're on the team.")

        if not await invoker_in_team_channel_vc(interaction):
            return await interaction.edit_original_response(
                content="You can only start a practice if you're in the team channel VC."
            )

        assert interaction.channel and not isinstance(
            interaction.channel,
            (discord.PartialMessageable, discord.StageChannel, discord.ForumChannel, discord.CategoryChannel),
        )

        category = interaction.channel.category
        assert category

        team = Team.from_category(category.id, bot=self.bot)

        # Let's check if there's already a practice going on for this team.
        for practice in self.bot.team_practice_cache.values():
            if practice.team == team:
                if practice.status is PracticeStatus.ongoing:
                    return await interaction.edit_original_response(
                        content="There's already a practice going on for this team, you can\'t start another one. "
                        "If this is a mistake reach out to a captain.",
                    )

        message = await interaction.channel.send(embed=self.bot.Embed(title='Creating practice, hold tight...'))

        # Awesome, we can create our practice persistent view now, send it, then enter this information
        # into the database.
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                """INSERT INTO teams.practice(
                    team_id, guild_id, status, initiated_at, initiated_by_id, message_id
                ) VALUES (
                    $1, $2, $3, $4, $5, $6
                )    
                RETURNING *
                """,
                team.id,
                interaction.guild and interaction.guild.id,
                PracticeStatus.ongoing.value,
                interaction.created_at,
                interaction.user.id,
                message.id,
            )
            assert data

            attending_data = await connection.fetchrow(
                "INSERT INTO teams.practice_attending(practice_id, member_id, joined_at) VALUES ($1, $2, $3) RETURNING *",
                data['id'],
                interaction.user.id,
                interaction.created_at,
            )
            assert attending_data

        practice = Practice(bot=self.bot, team=team, data=dict(data), attending=[])
        attending_member = AttendingMember(practice=practice, data=dict(attending_data))
        practice.attending_members[attending_member.member_id] = attending_member

        # Let's append this practice to the bot's cache
        self.bot.team_practice_cache[practice.id] = practice

        # Now we can create our view and edit the message
        view = PracticeView(practice)
        await message.edit(embed=practice.embed, view=view)

        await interaction.edit_original_response(
            content="A new practice has been created. Do not leave the voice channel until the practice is over."
        )

    @commands.Cog.listener('on_voice_state_update')
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return

        channel = after.channel
        if channel is not None:
            # This member probably *joined* a voice channel, let's check if it's a team channel
            # and if there's an ongoing practice.
            category = channel.category
            if category is None:
                # This can't be a team
                return

            # Let's try and see if this is a team channel from the category
            try:
                team = Team.from_category(category.id, bot=self.bot)
            except Exception:
                # This isn't a team channel
                return

            ongoing_practice = team.ongoing_practice
            if ongoing_practice is None:
                # There is no practice, so we can't do anything
                return

            # There is an ongoing practice, let's check if this member is on the team
            if team.get_member(member.id) is None:
                # This member isn't on the team
                return

            # Awesome, this member is on the team and there's an ongoing practice, let's check if they're
            # already attending.
            if member.id in ongoing_practice.attending_members:
                # They're already attending, so we can't do anything
                return

            # Let's handle a new member joining the practice
            return await ongoing_practice.handle_attending_member_join(member, joined_at=discord.utils.utcnow())

        # Let's check to see if we need to be removing this member from an ongoing practice.

        # it's known this channel is None now, let's check to make sure the member *left* a channel
        # and that it's in a team like before.
        if before.channel is None:
            # This member didn't leave a channel, so we can't do anything
            return

        # This member left a channel, let's check if it's a team channel
        category = before.channel.category
        if category is None:
            # This can't be a team
            return

        # Let's try and see if this is a team channel from the category
        try:
            team = Team.from_category(category.id, bot=self.bot)
        except Exception:
            # This isn't a team channel
            return

        ongoing_practice = team.ongoing_practice
        if ongoing_practice is None:
            # There is no practice, so we can't do anything
            return

        # There is an ongoing practice, let's check if this member is on the team
        if team.get_member(member.id) is None:
            # This member isn't on the team, we can't add them to the ongoing practice.
            return

        # Awesome, this member is on the team and there's an ongoing practice, let's check if they're
        # already attending.
        if member.id not in ongoing_practice.attending_members:
            # They're not attending, so we can't remove them.
            return

        # Awesome, this member is on the team, there's an ongoing practice, and they're attending.
        # Let's handle them leaving the practice.
        await ongoing_practice.handle_attending_member_leave(member, discord.utils.utcnow())


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(TeamPractices(bot))
