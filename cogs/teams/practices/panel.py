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

import datetime
import pytz
import discord
from utils import BaseView, BaseViewKwargs, human_timedelta, default_button_doc_string, SelectOneOfMany, UserSelect

from typing import TYPE_CHECKING, List, Tuple, Union
from typing_extensions import Unpack, Self

if TYPE_CHECKING:
    from bot import FuryBot
    from .practice import Practice, PracticeMember
    from ..team import Team

__all__: Tuple[str, ...] = ('TeamPracticesPanel', 'PracticePanel', 'PracticeMemberPanel')

EST = pytz.timezone("Us/Eastern")


class PracticeMemberPanel(BaseView):
    """A view to manage a practice member.

    This view is launched from the :class:`TeamPracticeView` view.

    Parameters
    Attributes
    ----------
    member: :class:`.PracticeMember`
        The practice member to manage.
    discord_member: :class:`discord.Member`
        The :class:`discord.Member` object representing the member.
    """

    def __init__(self, member: PracticeMember, discord_member: discord.Member, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.member: PracticeMember = member
        self.discord_member: discord.Member = discord_member

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing this practice member."""
        practice = self.member.practice

        embed = practice.team.embed(
            title='Practice Information',
            description=f'**Practice Started At**: {practice.format_start_time()}\n'
            f'**Practice Ended At**: {practice.format_end_time() or "This practice is in progress..."}\n',
        )

        if not self.member.attending:
            embed.add_field(
                name='Not Attending',
                value=f'This member has marked themselves as not attending this practice.\n**Reason**: {self.member.reason}',
            )

        total_time = sum(total_time.total_seconds() for history in self.member.history if (total_time := history.total_time))
        embed.add_field(
            name='Total Time Practicing This Session',
            value=f'In this session, this member has spent **{human_timedelta(total_time)}** practicing.',
        )

        for count, history in enumerate(self.member.history, start=1):

            left_at = (
                history.left_at
                and f'{discord.utils.format_dt(history.left_at, "T")} ({discord.utils.format_dt(history.left_at, "R")})'
            )
            total_time = (
                f'**Total Time:** {human_timedelta((history.left_at - history.joined_at).total_seconds())}'
                if history.left_at
                else f'**Practicing For:** {human_timedelta((discord.utils.utcnow() - history.joined_at).total_seconds())}'
            )

            embed.add_field(
                name=f'VC History #{count}',
                value=f'**Joined At**: {discord.utils.format_dt(history.joined_at, "T")} ({discord.utils.format_dt(history.joined_at, "R")})\n'
                f'**Left At**: {left_at or "Member is still in this practice..."}\n'
                f'{total_time}',
                inline=False,
            )

        return embed

    @discord.ui.button(label='Delete Member From Practice')
    @default_button_doc_string
    async def delete_member_from_practice(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Deletes the given member from this practice and acts if they never attended in the first place."""
        await self.member.delete()

        view = PracticePanel(self.member.practice, target=interaction)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    # TODO: Add buttons for removing a history from this member.


class PracticePanel(BaseView):
    """Represents the view for a practice.

    Parameters
    Attributes
    ----------
    practice: :class:`.Practice`
        The practice to represent.
    """

    def __init__(self, practice: Practice, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.practice: Practice = practice

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing this practice."""
        embed = self.practice.team.embed(
            title="Practice Information",
            description='Below is some inforamtion for the given practice. Use the buttons below to view stats about '
            'specific members who attended this practice.\n'
            f'- **Started At**: {self.practice.format_start_time()}\n'
            f'- **Ended At**: {self.practice.format_end_time() or "This practice is in progres..."}\n',
        )

        attending_member_mentions: List[str] = [member.mention for member in self.practice.attending_members]
        excused_member_mentions: List[str] = [member.mention for member in self.practice.excused_members]
        members_unattended_mentions: List[str] = [member.mention for member in self.practice.missing_members]

        embed.add_field(
            name='Members Attended',
            value='\n'.join(attending_member_mentions),
            inline=False,
        )

        if excused_member_mentions:
            embed.add_field(name='Excused Members', value='\n'.join(excused_member_mentions), inline=False)

        if members_unattended_mentions:
            embed.add_field(name='Members Unattended', value='\n'.join(members_unattended_mentions), inline=False)

        return embed

    @discord.ui.button(label="End Practice")
    @default_button_doc_string
    async def end_practice(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Ends the practice."""
        if not self.practice.ongoing:
            return await interaction.response.send_message(
                "This practice is not ongoing, you cannot end a practice that has already ended.", ephemeral=True
            )

        await interaction.response.defer()

        # Because we're manually ending this, we need to edit all members currently in the practice so that they have
        # a left_at time.
        for member in self.practice.members:
            if member.attending:
                await member.handle_leave(when=interaction.created_at)

        await self.practice.end()

        assert interaction.message
        await interaction.message.edit(embed=self.embed, view=self)

    async def _manage_practice_members_after(
        self, interaction: discord.Interaction[FuryBot], users: List[Union[discord.Member, discord.User]]
    ) -> None:
        selected = users[0]
        assert isinstance(selected, discord.Member)

        if self.practice.team.get_member(selected.id) is None:
            await interaction.response.edit_message(view=self, embed=self.embed)
            return await interaction.followup.send(
                f'{selected.mention} is not on this team, there\'s nothing to edit.', ephemeral=True
            )

        practice_member = self.practice.get_member(selected.id)
        if practice_member is None:
            await interaction.response.edit_message(view=self, embed=self.embed)
            return await interaction.followup.send(
                f'{selected.mention} is not in this practice, there\'s nothing to edit.', ephemeral=True
            )

        view = self.create_child(PracticeMemberPanel, practice_member, selected)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label="Manage Practice Members")
    @default_button_doc_string
    async def manage_practice_members(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Manage a specific member in this practice."""
        UserSelect(
            after=self._manage_practice_members_after, parent=self, placeholder="Select a member to manage...", max_values=1
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Delete Practice')
    @default_button_doc_string
    async def delete_button(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Delete this practice from the database."""
        if self.practice.ongoing:
            return await interaction.response.send_message('You can\'t delete a practice that is ongoing.', ephemeral=True)

        await self.practice.delete()

        # Go back a parent view
        view = TeamPracticesPanel(team=self.practice.team, target=interaction, parent=None)
        await interaction.response.edit_message(view=view, embed=view.embed)


class TeamPracticesPanel(BaseView):
    """Represents a view for displaying and managing a team's practices.

    Parameters
    Attributes
    ----------
    team: :class:`Team`
        The team to display practices for.
    """

    def __init__(self, team: Team, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: Displays team statistics for practices."""

        embed = self.team.embed(
            title="Practices.",
            description=f"This team has had **{len(self.team.practices)}** practices in total.",
        )

        # Get the average number of members per practice
        # Get the average total time in a practice.
        if len(self.team.practices) > 0:
            average_number_of_members = sum(len(p.members) for p in self.team.practices) / len(self.team.practices)
            average_time = self.team.get_total_practice_time() / len(self.team.practices)
        else:
            average_number_of_members = 0
            average_time = datetime.timedelta()

        embed.add_field(
            name='Average Number of Members', value=f'**{average_number_of_members:.2f}** members.', inline=False
        )

        embed.add_field(
            name='Average Practice Time', value=f'**{human_timedelta(average_time.total_seconds())}** total.', inline=False
        )

        # The total number of practices done "in a row". The longest streak of practices (a streak breaks if there is 8 days without a practice)
        streak = self.team.get_practice_streak()
        if streak != 0:
            embed.add_field(
                name="Longest Practice Streak",
                value=f"**{streak}** practices (8 days without a practice breaks the streak).",
                inline=False,
            )

        ranked_members = self.team.rank_member_practice_times()
        if ranked_members:
            embed.add_field(
                name="Top 5 Practice Times",
                value='\n'.join(
                    f'{member.mention}: {human_timedelta(time.total_seconds())}' for (member, time) in ranked_members[:5]
                ),
                inline=False,
            )

        absent_members = self.team.rank_member_absences()
        if absent_members:
            embed.add_field(
                name="Top 5 Absences",
                value='\n'.join(f'{member.mention}: {absences}' for (member, absences) in absent_members[:5]),
                inline=False,
            )

        return embed

    async def _manage_practice_after(self, interaction: discord.Interaction[FuryBot], values: List[str]) -> None:
        practice_id = int(values[0])
        practice = discord.utils.get(self.team.practices, id=practice_id)
        if not practice:
            await interaction.response.edit_message(view=self, embed=self.embed)
            return await interaction.followup.send("That practice doesn't exist anymore.", ephemeral=True)

        view = self.create_child(PracticePanel, practice)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label="Manage Practice")
    @default_button_doc_string
    async def manage_practice(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Manage a specific practice."""
        # A strftime string to turn a datetime into "Month Day, Hour:Minute AM/PM"
        date_format = '%B %d, %I:%M %p'

        options: List[discord.SelectOption] = []
        for practice in self.team.practices[:20]:
            # Practice.ended_at is in UTC, we need to convert it to EST to display it properly.
            # We also need to convert it to a datetime object to use strftime.
            ended_at = practice.ended_at and practice.ended_at.astimezone(tz=EST).strftime(date_format) or 'In Progress...'
            options.append(discord.SelectOption(label=ended_at, value=str(practice.id)))

        SelectOneOfMany(
            self,
            options=options,
            after=self._manage_practice_after,
        )

        return await interaction.response.edit_message(view=self)

    # TODO: Add a button to view complete practice history (see ID)
    # TODO: Add a button to get a practice by it's ID
