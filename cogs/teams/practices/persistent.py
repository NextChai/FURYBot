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

from typing import TYPE_CHECKING, List, Optional, Tuple

import discord
from typing_extensions import Self

from cogs.teams.errors import MemberNotOnTeam
from cogs.teams.practices.errors import MemberAlreadyInPractice
from utils import default_button_doc_string, human_timedelta

if TYPE_CHECKING:
    from bot import FuryBot

    from .practice import Practice, PracticeMember

__all__: Tuple[str, ...] = ('PracticeView', 'UnabletoAttendModal')


class UnabletoAttendModal(discord.ui.Modal):
    """A modal spawned from the :class:`PracticeView` when a member opts-out of a practice.

    Parameters
    ----------
    practice: :class:`Practice`
        The practice that the member is opting out of.
    member: :class:`discord.Member`
        The member that is opting out of the practice.
    """

    reason: discord.ui.TextInput[Self] = discord.ui.TextInput(
        label='Why Can\'t You Attend?',
        style=discord.TextStyle.long,
        custom_id="reason-to-not-attend",
        placeholder="Enter why you can\'t attend. This will not be shared with any of your team members.",
        required=True,
    )

    def __init__(self, *, practice: Practice, member: discord.Member) -> None:
        self.practice: Practice = practice
        self.member: discord.Member = member
        super().__init__(timeout=None, title="Why Can't You Attend?")

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        """|coro|

        A check to ensure that the interaction is from the member that is opting out of the practice.
        """
        if interaction.user != self.member:
            return await interaction.response.send_message("Hey! This isn\'t yours!", ephemeral=True)

        return True

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> None:
        """|coro|

        Called when the modal has been submitted. Will handle the member opting out of the practice
        and complain to the invoker if they're not on the team or they've already opted out.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from the user pressing "Submit".
        """
        await interaction.response.defer()

        try:
            await self.practice.handle_member_unable_to_join(member=self.member, reason=self.reason.value)
        except MemberNotOnTeam:
            return await interaction.followup.send('Hey! You aren\'t on this team, you can\'t do this!', ephemeral=True)
        except MemberAlreadyInPractice:
            return await interaction.followup.send(
                'Hey! You are already registered to be in this practice. '
                'If you can\'t attend leave your teams voice channel and it\'ll be marked accordingly.',
                ephemeral=True,
            )

        await interaction.followup.send("Thanks for letting me know, I\'ve made a mark on your record.", ephemeral=True)


class PracticeView(discord.ui.View):
    """The persistent practice view creates when a practice is created.

    Parameters
    ----------
    practice: :class:`Practice`
        The practice that the persistent view is being created for.
    """

    def __init__(self, practice: Practice) -> None:
        self.practice: Practice = practice
        super().__init__(timeout=None)

    @property
    def _practice_done_embed(self) -> discord.Embed:
        team = self.practice.team
        started_by = self.practice.started_by

        attending_member_mentions: List[str] = [member.mention for member in self.practice.attending_members]
        excused_member_mentions: List[str] = [member.mention for member in self.practice.excused_members]
        members_unattended_mentions: List[str] = [member.mention for member in self.practice.missing_members]

        embed = self.practice.team.embed(
            title=f'{team.display_name} Practice.',
            description=f'A practice started by {started_by.mention} on {self.practice.format_start_time()} is currently in progress has come to an end.',
        )

        # Show the members that attended the practice.
        embed.add_field(
            name='Members Attended',
            value='\n'.join(attending_member_mentions),
            inline=False,
        )

        if excused_member_mentions:
            embed.add_field(name='Excused Members', value='\n'.join(excused_member_mentions), inline=False)

        if members_unattended_mentions:
            embed.add_field(name='Members Unattended', value='\n'.join(members_unattended_mentions), inline=False)

        total_time = self.practice.get_total_practice_time()
        assert total_time

        embed.add_field(
            name='Total Practice Time',
            value=f'In total, **todays practice was {human_timedelta(total_time.total_seconds())}**. More stats have been posted '
            'in the practice completed message.',
        )

        return embed

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Emebd`: The embed that is displayed in the persistent view for this practice."""
        if not self.practice.ongoing:
            return self._practice_done_embed

        team = self.practice.team
        started_by = self.practice.started_by

        embed = team.embed(
            title=f'{team.display_name} Practice.',
            description=f'A practice started by {started_by.mention} on {self.practice.format_start_time()} '
            'is currently in progress.',
        )

        embed.add_field(name='Voice Channel', value=self.practice.team.voice_channel.mention, inline=False)

        attending_members: List[PracticeMember] = []
        unable_to_attend: List[PracticeMember] = []
        for member in self.practice.members:
            if not member.attending:
                unable_to_attend.append(member)
            else:
                attending_members.append(member)

        embed.add_field(
            name='Attending Members',
            value='\n'.join([member.mention for member in attending_members]),
            inline=False,
        )

        if unable_to_attend:
            embed.add_field(
                name='Unable to Attend', value='\n'.join([member.mention for member in unable_to_attend]), inline=False
            )

        embed.add_field(
            name='How Do I Attend?',
            value=f'**To attend your team practice, join your team\'s voice channel, {team.voice_channel.mention}. '
            'Your team practice time will be recorded once you leave the voice channel.**',
            inline=False,
        )

        embed.add_field(
            name='I Can\'t Attend!',
            value='Press the "I Can\'t Attend" button below to let us know why you can\'t attend. '
            'This will be recorded on your attendance record.',
        )

        return embed

    async def update_message(self) -> None:
        """|coro|

        Updates the message this persistent view is attached to with the updated embed.

        This is called whenever a practice member joins or leaves a voice channel.
        """
        message_id = self.practice.message_id
        message = await self.practice.team.text_channel.fetch_message(message_id)
        await message.edit(view=self, embed=self.embed)

    @discord.ui.button(label="I Can\'t Attend", style=discord.ButtonStyle.red, custom_id='unable-to-attend')
    @default_button_doc_string
    async def handle_unable_to_attend(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Called when the user presses the "I Can't Attend" button.". Will spawn the unable to attend modal."""
        assert isinstance(interaction.user, discord.Member)
        await interaction.response.send_modal(UnabletoAttendModal(practice=self.practice, member=interaction.user))
