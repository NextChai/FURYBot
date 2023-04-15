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

from typing import TYPE_CHECKING, Dict, Optional

import discord
from typing_extensions import Self

from utils import AfterModal, TimerNotFound, human_join, human_timestamp

if TYPE_CHECKING:
    from bot import FuryBot

    from ...team import TeamMember
    from ..gameday import Gameday, GamedayMember


class AttendanceVotingView(discord.ui.View):
    """A dynamic view that allows users to vote on attendance for a gameday."""

    def create_voting_done_embed(self, gameday: Gameday, /) -> discord.Embed:
        team = gameday.team
        if team is None:
            raise ValueError('Gameday is missing a team.')

        embed = team.embed(
            title='Gameday Voting Confirmed',
            description='This gameday has reached the required amount of votes to confirm this gameday. There is no further '
            f'actions required from you. This gameday is scheduled to start at {human_timestamp(gameday.starts_at)}.',
        )

        attending_members: Dict[int, GamedayMember] = {}
        not_attending_members: Dict[int, GamedayMember] = {}

        for member in gameday.members.values():
            if member.is_attending:
                attending_members[member.id] = member
            else:
                not_attending_members[member.id] = member

        embed.add_field(
            name='Attending Members',
            value=human_join((m.mention for m in attending_members.values()))
            or 'No members have marked themselves as attending.',
            inline=False,
        )
        embed.add_field(
            name='Not Attending Members',
            value='\n'.join(f'{member.mention}: {member.reason}' for member in not_attending_members.values())
            or 'No members have marked themselves as not attending.',
            inline=False,
        )

        return embed

    def create_embed(self, gameday: Gameday) -> discord.Embed:
        team = gameday.team
        if team is None:
            raise ValueError('Gameday is missing a team.')

        if gameday.voting.has_votes_needed:
            embed = self.create_voting_done_embed(gameday)
            embed.set_footer(
                text='Because this gameday has reached the end of voting before it naturally ends, I\'ve '
                'scheduled the voting to end soon, you\'ll get another message here shortly.'
            )

            return embed

        embed = team.embed(
            title=f'Gameday Attendance Voting For {human_timestamp(gameday.starts_at)} gameday.',
            description=f'**Voting Started At**: {human_timestamp(gameday.voting.starts_at)}\n'
            f'**Voting Ends At**: {human_timestamp(gameday.voting.ends_at)}',
        )

        attending_members: Dict[int, GamedayMember] = {}
        not_attending_members: Dict[int, GamedayMember] = {}

        for member in gameday.members.values():
            if member.is_attending:
                attending_members[member.member_id] = member
            else:
                not_attending_members[member.member_id] = member

        waiting_on_members: Dict[int, TeamMember] = {
            team_member.member_id: team_member
            for team_member in team.members
            if team_member.member_id not in attending_members
            and team_member.member_id not in not_attending_members
            and not team_member.is_sub
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
        return bool(await self._get_current_gameday(interaction))

    async def _get_current_gameday(self, interaction: discord.Interaction[FuryBot]) -> Optional[Gameday]:
        guild_id = interaction.guild_id
        if guild_id is None:
            await interaction.response.send_message('You can only use this in a server.', ephemeral=True)
            return None

        # Let's try and find the given team from this interaction channel
        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.response.send_message('You can only use this in a team channel.', ephemeral=True)
            return None

        message_id = interaction.message and interaction.message.id
        if message_id is None:
            await interaction.response.send_message(
                'The message found on this interaction is missing, how did you do this? Contact a developer.', ephemeral=True
            )
            return None

        team = interaction.client.get_team_from_channel(channel_id, guild_id)
        if team is None:
            await interaction.response.send_message('You can only use this in a team channel.', ephemeral=True)
            return None

        team_member = team.get_member(interaction.user.id)
        if team_member is None:
            await interaction.response.send_message(
                'You are not a member of this team, you can not do this action.', ephemeral=True
            )
            return None

        bucket = team.get_gameday_bucket()
        if bucket is None:
            await interaction.response.send_message('This team has no gameday bucket, you can not use this!', ephemeral=True)
            return None

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
            return None

        if valid_gameday.voting.has_votes_needed:
            await interaction.response.send_message(
                'This gameday has already reached the required amount of votes to confirm this gameday.', ephemeral=True
            )
            return None

        if team_member.is_sub:
            # If all team members on the main roster have voted, we can skip this check
            # and allow all subs to vote.
            main_roster_ids = {member.member_id for member in team.main_roster}
            all_main_roster_members_voted = all(
                (member.member_id in main_roster_ids for member in valid_gameday.members.values())
            )

            # TODO: Dynamically check if the sub could vote based on whether or not all available
            # main roster members could even finish the gameday per team rules..?

            if not all_main_roster_members_voted:
                await interaction.response.send_message(
                    'You are a sub! At this time, voting is only open to the members on the main roster of the team. After all '
                    'the team\'s main roster has voted, you can use this voting message to mark yourself as attending in their place.',
                    ephemeral=True,
                )
                return None

        gameday_member = valid_gameday.get_member(interaction.user.id)
        if gameday_member is not None:
            await interaction.response.send_message(
                'You are already a member of this gameday, you can not vote on this.', ephemeral=True
            )
            return None

        return valid_gameday

    @discord.ui.button(label='I Can Attend', style=discord.ButtonStyle.green, custom_id='attendance-voting-view:can-attend')
    async def attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = await self._get_current_gameday(interaction)
        if gameday is None:
            return

        await interaction.response.defer()

        # Double check again to see if voting is filled
        if gameday.voting.has_votes_needed:
            await interaction.followup.send(
                'This gameday has already reached the required amount of votes to confirm this gameday. At this time '
                'you can not do this action.',
                ephemeral=True,
            )
            return

        async with interaction.client.safe_connection() as connection:
            await gameday.create_member(interaction.user.id, connection=connection)

            embed = self.create_embed(gameday)

            if gameday.voting.has_votes_needed:
                # We need to edit the timer so it expires in 5 minutes.
                try:
                    voting_ends_at_timer = await gameday.voting.fetch_ends_at_timer(connection=connection)
                except TimerNotFound:
                    pass
                else:
                    if voting_ends_at_timer is not None:
                        await voting_ends_at_timer.edit(expires=interaction.created_at)

                await interaction.edit_original_response(embed=embed, view=None, content=None)
            else:
                await interaction.edit_original_response(embed=embed)

    async def _not_attend_after(
        self, interaction: discord.Interaction[FuryBot], reason_input: discord.ui.TextInput[AfterModal], *, gameday: Gameday
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        if gameday.voting.has_votes_needed:
            await interaction.followup.send(
                'This gameday has already reached the required amount of votes to confirm this gameday. At this time '
                'this action does not matter.',
                ephemeral=True,
            )

        async with interaction.client.safe_connection() as connection:
            await gameday.create_member(interaction.user.id, reason=reason_input.value, connection=connection)

        embed = self.create_embed(gameday)
        return await interaction.edit_original_response(embed=embed)

    @discord.ui.button(
        label='I Can Not Attend', style=discord.ButtonStyle.red, custom_id='attendance-voting-view:can-not-attend'
    )
    async def not_attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = await self._get_current_gameday(interaction)
        if gameday is None:
            return

        modal = AfterModal(
            interaction.client,
            self._not_attend_after,
            discord.ui.TextInput(
                label='Missing Gameday', placeholder='Enter why you can not attend here...', style=discord.TextStyle.long
            ),
            title='Why Can You Not Attend?',
            timeout=None,
            gameday=gameday,
        )
        await interaction.response.send_modal(modal)
