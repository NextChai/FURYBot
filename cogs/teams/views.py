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
import functools
from typing import TYPE_CHECKING, Any, List, Optional, cast

import discord
import pytz
from typing_extensions import Self, Unpack

from cogs.teams.scrim.persistent import AwayConfirm, HomeConfirm
from utils import (
    CHANNEL_EMOJI_MAPPING,
    AutoRemoveSelect,
    BaseView,
    BaseViewKwargs,
    BasicInputModal,
    TimeTransformer,
    default_button_doc_string,
    human_timedelta,
)

from . import ScrimStatus
from .team import TeamMember

if TYPE_CHECKING:
    from .practices import Practice, PracticeMember
    from .scrim import Scrim
    from .team import Team

EST = pytz.timezone("Us/Eastern")


def clamp(minimum: Optional[int], maximum: int) -> int:
    if minimum is None:
        return maximum

    if minimum <= 0:
        return 1

    # Return the minimum if its less than or equal the maximum else the maximum.
    # If the minimum is 0 though, return 1 in replace of it.
    return minimum if minimum <= maximum else maximum


class TeamMemberPracticeStatisticsView(BaseView):
    """"""

    def __init__(self, member: TeamMember, discord_member: discord.Member, *args: Any, **kwargs: Any) -> None:
        self.member: TeamMember = member
        self.discord_member: discord.Member = discord_member
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        team = self.member.team
        embed = team.embed(title="Practice Statistics")

        # Get the: total time, total amount, total started, absences
        total, absences, started_by = 0, 0, 0
        total_time: datetime.timedelta = datetime.timedelta()
        last_attended: Optional[Practice] = None
        for practice in team.practices:
            member = practice.get_member(self.discord_member.id)
            if member is None:
                absences += 1
                continue

            total += 1
            total_time += member.get_total_practice_time()

            if practice.started_by == member:
                started_by += 1

            if last_attended is None:
                last_attended = practice
            elif last_attended.started_at < practice.started_at:
                last_attended = practice

        # Get the current streak of attended practices
        current_streak = 0
        for practice in sorted(team.practices, key=lambda p: p.started_at, reverse=True):
            member = practice.get_member(self.discord_member.id)
            if member is None:
                current_streak = 0
                continue

            current_streak += 1

        total_team_practices = len(team.practices)
        percentage_of_attended_practices = (total / total_team_practices) * 100

        embed.add_field(
            name='Attended Practices',
            value=f'**Count**: {total}\n**Percentage**: {percentage_of_attended_practices:.2f}%',
            inline=False,
        )

        percentage_of_absences = (absences / total_team_practices) * 100
        embed.add_field(
            name='Absences',
            value=f'**Absences**: {absences}\n**Percentage**: {percentage_of_absences:.2f}%',
            inline=False,
        )

        started_by_percentage = (started_by / total) * 100
        embed.add_field(
            name='Started Practices',
            value=f'**Total**: {started_by}\n**Percentage**: {started_by_percentage:.2f}%',
            inline=False,
        )

        embed.add_field(
            name='Practice Time',
            value=f'**Total**: {human_timedelta(total_time.total_seconds())}\n**Average**: {human_timedelta(total_time.total_seconds() / total)}',
            inline=False,
        )

        embed.add_field(name='Streaks', value=f'**Current Streak**: {current_streak}\n')

        last_attended_fmt = (
            last_attended
            and f'**Started At**: {last_attended.format_start_time()}\n**Ended At**: {last_attended.format_end_time()}'
            or 'Has never attended a practice.'
        )
        embed.add_field(name='Last Attended Practice', value=last_attended_fmt, inline=False)

        return embed


class TeamMemberView(BaseView):
    """A view used to manage a team member.

    Parameters
    ----------
    member: :class:`.TeamMember`
        The member to manage.

    Attributes
    ----------
    :class:`.TeamMember`
        The member to manage.
    """

    def __init__(self, member: discord.Member, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.member: discord.Member = member
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.team.embed(title='Manage Team Member.', author=self.member)

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        embed.add_field(name='Is Sub?', value='Member is a sub.' if team_member.is_sub else 'Member is not a sub.')

        return embed

    @discord.ui.button(label='Toggle Role')
    @default_button_doc_string
    async def toggle_role(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Swap the members role on the team. If they're on the main roster they'll be moved to a sub, and vice versa."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        coro = team_member.promote if team_member.is_sub else team_member.demote
        await coro()

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Member')
    @default_button_doc_string
    async def remove_member(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Remove this member from the team."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        await team_member.remove_from_team()

        view = TeamMembersView(self.team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @discord.ui.button(label='View Practice Statistics')
    @default_button_doc_string
    async def view_practice_statistics(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """View the practice statistics for this member."""
        team_member = self.team.get_member(self.member.id)
        assert team_member

        view = self.create_child(TeamMemberPracticeStatisticsView, team_member, self.member)
        await interaction.response.edit_message(view=view, embed=view.embed)


class TeamMembersView(BaseView):
    """A view used to manage team members.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        member_metadata: List[str] = []

        for member in self.team.team_members.values():
            member_metadata.append(f'{member.mention}: {"**Is a sub.**" if member.is_sub else "**On the main roster.**"}')

        embed = self.team.embed(
            title=f'Team Members',
            description='Use the buttons below to manage team members.\n\n{}'.format(
                "\n".join(member_metadata) or 'Team has no members.'
            ),
        )

        return embed

    async def _manage_member_after(self, select: discord.ui.UserSelect[Self], interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        team_member = self.team.get_member(select.values[0].id)
        if not team_member:
            await interaction.edit_original_response(embed=self.embed, view=self)
            await interaction.followup.send('This member is not on the team.', ephemeral=True)
            return

        member = cast(discord.Member, select.values[0])
        view = self.create_child(TeamMemberView, member=member, team=self.team)
        await interaction.edit_original_response(embed=view.embed, view=view)

    async def _manage_member_assignment(
        self,
        select: discord.ui.UserSelect[Self],
        interaction: discord.Interaction,
        *,
        assign_sub: bool = False,
        remove_member: bool = False,
    ) -> None:
        await interaction.response.defer()

        for member in select.values:
            if remove_member:
                team_member = self.team.get_member(member.id)
                if team_member is not None:
                    await self.team.remove_team_member(team_member)
            else:
                team_member = self.team.get_member(member.id)
                if team_member is None:
                    await self.team.add_team_member(member.id, is_sub=assign_sub)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Manage Member')
    @default_button_doc_string
    async def manage_member(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage this member on the team. You can remove them from it and demote them to a sub."""
        AutoRemoveSelect(item=discord.ui.UserSelect[Self](), parent=self, callback=self._manage_member_after)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Add Members')
    @default_button_doc_string
    async def add_members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add members to this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to add...'
            ),
            parent=self,
            callback=self._manage_member_assignment,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Members')
    @default_button_doc_string
    async def remove_members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove members from this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to remove...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, remove_member=True),
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Add Subs')
    @default_button_doc_string
    async def add_subs(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add subs to this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select a subs to add...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, assign_sub=True),
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Subs')
    @default_button_doc_string
    async def remove_subs(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove subs from this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select subs to remove...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, remove_member=True),
        )
        return await interaction.response.edit_message(view=self)


class ScrimView(BaseView):
    """Represents a view used to manage a scrim.

    Parameters
    ----------
    team: :class:`.Team`
        The team currently being viewed in the view history.
    scrim: :class:`.Scrim`
        The scrim to manage.

    Attributes
    ----------
    team: :class:`.Team`
        The team currently being viewed in the view history.
    scrim: :class:`.Scrim`
        The scrim to manage.
    """

    def __init__(self, team: Team, scrim: Scrim, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        self.scrim: Scrim = scrim
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.team.embed(
            title='Team Scrim Information',
            description=f'This scrim was originally scheduled for {self.scrim.scheduled_for_formatted()}. This scrim is currently **{self.scrim.status.value.replace("_", " ").title()}**.',
        )
        embed.add_field(
            name='Home Team',
            value=f'{self.scrim.home_team.display_name}\n**Confirmed Members**: {", ".join([m.mention for m in self.scrim.home_voters]) or "No home voters."}',
            inline=False,
        )
        embed.add_field(
            name='Away Team',
            value=f'{self.scrim.away_team.display_name}\n**Confirmed Members**: {", ".join([m.mention for m in self.scrim.away_voters]) or "No away voters."}',
        )

        if self.scrim.status is ScrimStatus.scheduled and self.scrim.scheduled_for < discord.utils.utcnow():
            # This scrim has started
            addition = ''
            if self.scrim.scrim_chat:
                addition = f' The scrim chat is {self.scrim.scrim_chat.mention}'

            embed.add_field(
                name='Scrim In Progress', value=f'This scrim is **currently in progress**.{addition}', inline=False
            )

        embed.set_author(name=self.scrim.home_team.display_name, icon_url=self.scrim.home_team.logo)

        embed.set_footer(text=f'Scrim ID: {self.scrim.id}')
        return embed

    async def _reschedule_scrim_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        # Let's try and parse this time
        value = modal.children[0].value
        try:
            transformed = await TimeTransformer('n/a').transform(interaction, value)
        except Exception as exc:
            await interaction.edit_original_response(embed=self.embed, view=self)
            return await interaction.followup.send(content=str(exc), ephemeral=True)

        assert transformed.dt
        await self.scrim.reschedle(transformed.dt, editor=interaction.user)
        await interaction.edit_original_response(
            content=f'I\'ve rescheduled this scrim for {self.scrim.scheduled_for_formatted()}.'
        )

    async def _manage_member_assignment(
        self, select: discord.ui.UserSelect[Self], interaction: discord.Interaction, *, add_vote: bool = True
    ) -> None:
        await interaction.response.defer()

        home_team = self.scrim.home_team
        away_team = self.scrim.away_team

        for member in select.values:
            home_member = home_team.get_member(member.id)
            team = home_team if home_member is not None else away_team

            if add_vote:
                await self.scrim.add_vote(member.id, team.id)
            else:
                await self.scrim.remove_vote(member.id, team.id)

        # Let's say we're removing / adding votes and the scrim is now scheduled due
        # to the votes, we should let the team know. #
        # NOTE: We wont cancel the scrim when we force remove votes.
        if self.scrim.status is ScrimStatus.pending_host and self.scrim.home_all_voted:
            # We need to update the scrim status to pending away and send the message
            await self.scrim.change_status(ScrimStatus.pending_away)

            view = HomeConfirm(self.scrim)
            home_message = await self.scrim.home_message()
            await home_message.edit(view=None, embed=view.embed)

            # Send the message to the other channel now
            view = AwayConfirm(self.scrim)
            away_message = await self.scrim.away_team.text_channel.send(embed=view.embed, view=view)
            await self.scrim.edit(away_message_id=away_message.id)

        elif self.scrim.status is ScrimStatus.pending_away and self.scrim.away_all_voted:
            # We need to change the status to scheduled and edit the messages
            await self.scrim.change_status(ScrimStatus.scheduled)

            view = HomeConfirm(self.scrim)
            home_message = await self.scrim.home_message()
            await home_message.edit(view=None, embed=view.embed)

            view = AwayConfirm(self.scrim)
            away_message = await self.scrim.away_message()
            if away_message:
                await away_message.edit(view=None, embed=view.embed)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Reschedule')
    @default_button_doc_string
    async def reschedule_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Reschedule this scrim to a later date."""
        # If this scrim has already started, we can't reschedule it
        if self.scrim.scheduled_for < interaction.created_at:
            return await interaction.response.send_message(
                'This scrim has already started, you cannot reschedule it.', ephemeral=True
            )

        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(self.bot, after=self._reschedule_scrim_after)
        modal.add_item(
            discord.ui.TextInput(label='When you want to reschedule this scrim to. For example: Tomorrow at 4pm.')
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Remove Confirmation')
    @default_button_doc_string
    async def remove_confirmation(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Forcefully remove confirmation for a member."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to remove confirmation for...'
            ),
            callback=functools.partial(self._manage_member_assignment, add_vote=False),
            parent=self,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Add Confirmation')
    @default_button_doc_string
    async def force_add_confirmation(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Forcefully add confirmation for a member."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to remove confirmation for...'
            ),
            callback=self._manage_member_assignment,
            parent=self,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Schedule Scrim')
    @default_button_doc_string
    async def force_schedule_scrim(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        """Forcefully set the scrim\'s status to :attr:`.ScrimStatus.scheduled`. This can not be done if the home team hasn't confirmed."""
        if not self.scrim.away_message_id:
            return await interaction.response.send_message(
                'You can not force start a scrim that has not been confirmed by the home team.', ephemeral=True
            )

        await interaction.response.defer()

        await self.scrim.change_status(ScrimStatus.scheduled)

        # Update the home message
        home_message = await self.scrim.home_message()
        view = HomeConfirm(self.scrim)
        await home_message.edit(embed=view.embed, view=None)

        # Update the away message
        away_message = await self.scrim.away_message()
        if away_message:
            view = AwayConfirm(self.scrim)
            await away_message.edit(embed=view.embed, view=None)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Cancel Scrim', style=discord.ButtonStyle.danger)
    @default_button_doc_string
    async def cancel_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Force cancel the scrim and remove it from the database."""
        await interaction.response.defer()
        await self.scrim.cancel()

        # Go back to the TeamScrimsView, the parent of this view, and edit the original response.
        # We can't go back in the parent tree because I dont want the user to try and edit
        # a cancelled scrim.
        view = TeamScrimsView(self.team, target=self.target)
        await interaction.edit_original_response(embed=view.embed, view=view)


class TeamScrimsView(BaseView):
    """A view used to manage a teams scrims, alter times, etc.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.team.embed(title="Scrims")

        hosted_scrims: int = 0
        for scrim in self.team.scrims:
            if scrim.home_team == self.team:
                hosted_scrims += 1

            embed.add_field(
                name=f'Scrim {discord.utils.format_dt(scrim.scheduled_for, "R")}',
                value=f'**Team Created Scrim**: {scrim.home_team.display_name}\n'
                f'**Away Team**: {scrim.away_team.display_name}\n'
                f'**Status**: {scrim.status.value.title()}\n'
                f'**Home Team Confirmed**: {", ".join([m.mention for m in scrim.home_voters]) or "No home votes."}\n'
                f'**Away Team Confirmed**: {", ".join([m.mention for m in scrim.away_voters]) or "No away votes."}\n',
            )

        embed.description = f'**{len(self.team.scrims)}** scrims total, **{hosted_scrims}** of which they are hosting.'

        if hosted_scrims == 0:
            embed.add_field(name='No Scrims', value='This team has no scrims.')

        return embed

    async def _manage_a_scrim_callback(self, select: discord.ui.Select[Any], interaction: discord.Interaction) -> None:
        scrim = discord.utils.get(self.team.scrims, id=int(select.values[0]))
        if not scrim:
            # Something really went wrong!
            return await interaction.response.edit_message(embed=self.embed, view=self)

        view = ScrimView(self.team, scrim, target=self.target)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Select a Scrim')
    @default_button_doc_string
    async def manage_a_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to select a scrim to manage."""
        if not self.team.scrims:
            return await interaction.response.send_message('This team has no scrims.', ephemeral=True)

        AutoRemoveSelect(
            item=discord.ui.Select[Self](
                placeholder='Select a scrim to manage...',
                options=[
                    discord.SelectOption(
                        label=scrim.scheduled_for.strftime("%A, %B %d, %Y at %I:%M %p"),
                        value=str(scrim.id),
                    )
                    for scrim in self.team.scrims
                ],
            ),
            parent=self,
            callback=self._manage_a_scrim_callback,
        )

        # The AutoRemoveSelect automatically removes all children
        # and adds itslef. Once the select has been completed it will
        # add the children back and call the "_manage_a_scrim_callback" callback for us.
        return await interaction.response.edit_message(view=self)


class TeamChannelsView(BaseView):
    """A view used to manage and view team channels.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """discord.Embed: The embed for this view."""
        embed = self.team.embed(title=f'Channels.')

        embed.add_field(name='Category Channel', value=self.team.category_channel.mention)
        embed.add_field(name='Text Channel', value=self.team.text_channel.mention)
        embed.add_field(name='Voice Channel', value=self.team.voice_channel.mention)
        embed.add_field(
            name='Extra Channels',
            value='\n'.join([c.mention for c in self.team.extra_channels]) or 'Team has no extra channels.',
        )

        return embed

    async def _create_extra_channel_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any], discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        channel_name: str = modal.children[0].value
        channel_type: str = modal.children[1].value

        meth_mapping = {
            'text': self.team.category_channel.create_text_channel,
            'voice': self.team.category_channel.create_voice_channel,
        }

        meth = meth_mapping.get(channel_type.lower(), None)
        if meth:
            channel = await meth(name=channel_name)

            extra_channel_ids = self.team.extra_channel_ids.copy()
            extra_channel_ids.append(channel.id)
            await self.team.edit(extra_channel_ids=extra_channel_ids)

        await interaction.edit_original_response(view=self, embed=self.embed)

    async def _delete_extra_channels_after(self, select: discord.ui.Select[Self], interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        # Get the new channel ids
        valid_extra_channel_ids = self.team.extra_channel_ids.copy()

        for str_channel_id in select.values:
            channel_id = int(str_channel_id)
            if channel_id in valid_extra_channel_ids:
                valid_extra_channel_ids.remove(channel_id)

            channel = self.guild.get_channel(int(str_channel_id))
            if channel is not None:
                await channel.delete()

        await self.team.edit(extra_channel_ids=valid_extra_channel_ids)

        await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Create Extra Channel')
    @default_button_doc_string
    async def create_extra_channel(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to create an extra channel for the team."""
        modal: BasicInputModal[discord.ui.TextInput[Any], discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot,
            after=self._create_extra_channel_after,
            title='Create Extra Channel',
            timeout=None,
        )
        modal.add_item(discord.ui.TextInput(label='Channel Name', placeholder='Enter the channel name...'))
        modal.add_item(discord.ui.TextInput(label='Channel Type', placeholder='"text" or "voice"...'))
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Delete Extra Channels')
    @default_button_doc_string
    async def delete_extra_channel(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to delete an extra channel for the team."""
        if not self.team.extra_channels:
            return await interaction.response.send_message('This team has no extra channels.', ephemeral=True)

        AutoRemoveSelect(
            item=discord.ui.Select[Self](
                max_values=clamp(len(self.team.extra_channel_ids), 25),
                placeholder='Select the channels to delete...',
                options=[
                    discord.SelectOption(
                        label=channel.name, value=str(channel.id), emoji=CHANNEL_EMOJI_MAPPING.get(type(channel), None)
                    )
                    for channel in self.team.extra_channels
                ],
            ),
            parent=self,
            callback=self._delete_extra_channels_after,
        )

        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Sync Channels')
    @default_button_doc_string
    async def sync_channels(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Syncs the channels for the team."""
        await interaction.response.defer()
        await self.team.sync()
        await interaction.edit_original_response(embed=self.embed)


class TeamNamingView(BaseView):
    """A view used to manage naming and renaming a team.


    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.team.embed(title='Customization', description=self.team.description or 'Team has no description.')
        embed.add_field(name='Team Nickname', value=self.team.nickname or 'Team has no nickname.', inline=False)
        embed.add_field(
            name='Team Logo', value=f'[Click here for logo.]({self.team.logo}).' or 'Team has no logo.', inline=False
        )

        return embed

    async def _perform_after(
        self, kwarg_name: str, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        value = modal.children[0].value
        await self.team.edit(**{kwarg_name: value})
        await interaction.edit_original_response(embed=self.embed, view=self)

    async def _rename_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after("name", modal, interaction)

    async def _change_nickname_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after("nickname", modal, interaction)

    async def _change_description_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after('description', modal, interaction)

    async def _change_logo_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after('logo', modal, interaction)

    @discord.ui.button(label='Rename')
    @default_button_doc_string
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Rename this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Rename Team', after=self._rename_after
        )
        modal.add_item(discord.ui.TextInput(label='New Name', placeholder='Enter a new name...', max_length=100))
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Nickname')
    @default_button_doc_string
    async def change_nickname(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the nickname of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Nickname', after=self._change_nickname_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Nickname', placeholder='Enter a new nickname...', max_length=100, required=False
            )
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Description')
    @default_button_doc_string
    async def change_description(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the description of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Nickname', after=self._change_description_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Description',
                placeholder='Enter a new description...',
                max_length=1024,
                required=False,
                style=discord.TextStyle.long,
            )
        )
        await interaction.response.send_modal(modal)

        await modal.wait()
        await self.team.text_channel.edit(topic=modal.children[0].value)

    @discord.ui.button(label='Change Logo')
    @default_button_doc_string
    async def change_logo(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the logo of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Logo', after=self._change_logo_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Logo',
                placeholder='Enter a new logo...',
                required=False,
                style=discord.TextStyle.short,
            )
        )
        await interaction.response.send_modal(modal)


class TeamCaptainsView(BaseView):
    """A view used to manage the captains of a team.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Any) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        embed = self.team.embed(
            title='Captains',
            description='Use the buttons below to manage team captain roles. This team '
            f'has **{len(self.team.captain_role_ids)}** captain(s).',
        )
        embed.add_field(
            name='Current Captains',
            value='\n'.join(r.mention for r in self.team.captain_roles) or 'This team has no current captains.',
        )

        return embed

    async def handle_captain_action(
        self, select: discord.ui.RoleSelect[Self], interaction: discord.Interaction, *, add: bool = True
    ) -> None:
        await interaction.response.defer()

        meth = self.team.add_captain if add else self.team.remove_captain
        for role in select.values:
            try:
                await meth(role.id)
            except Exception:
                pass

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Add Captains')
    @default_button_doc_string
    async def add_captain(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add a captain role to this team."""
        AutoRemoveSelect(
            item=discord.ui.RoleSelect[Self](max_values=clamp(len(self.team.captain_roles), 25)),
            parent=self,
            callback=self.handle_captain_action,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Captains')
    @default_button_doc_string
    async def remove_captain(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove a captain role from this team."""
        AutoRemoveSelect(
            item=discord.ui.RoleSelect[Self](max_values=clamp(len(self.team.captain_roles), 25)),
            parent=self,
            callback=functools.partial(self.handle_captain_action, add=False),
        )
        return await interaction.response.edit_message(view=self)


class TeamPracticeMemberView(BaseView):
    """A view to manage a practice member"""

    def __init__(self, member: PracticeMember, discord_member: discord.Member, *args: Any, **kwargs: Any) -> None:
        self.member: PracticeMember = member
        self.discord_member: discord.Member = discord_member
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
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


class TeamPracticeView(BaseView):
    def __init__(self, practice: Practice, *args: Any, **kwargs: Any) -> None:
        self.practice: Practice = practice
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
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
    async def end_practice(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
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
        self, select: discord.ui.UserSelect[Self], interaction: discord.Interaction
    ) -> None:
        selected: discord.Member = cast(discord.Member, select.values[0])  # This is in a guild so it'll resolve to Member

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

        view = self.create_child(TeamPracticeMemberView, practice_member, selected)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label="Manage Practice Members")
    @default_button_doc_string
    async def manage_practice_members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage a specific member in this practice."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](placeholder="Select a member to manage...", max_values=1),
            parent=self,
            callback=self._manage_practice_members_after,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Delete Practice From Database')
    @default_button_doc_string
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Delete this practice from the database."""
        if self.practice.ongoing:
            return await interaction.response.send_message('You can\'t delete a practice that is ongoing.', ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute("DELETE FROM teams.practice WHERE id = $1", self.practice.id)

        # Delete this practice from the bot's cache as well
        self.bot._team_practice_cache.get(self.practice.guild_id, {}).get(self.practice.team_id, {}).pop(
            self.practice.id, None
        )

        # Go back a parent view
        view = TeamPracticesView(team=self.practice.team, target=interaction, parent=None)
        await interaction.response.edit_message(view=view, embed=view.embed)


class TeamPracticesView(BaseView):
    """"""

    def __init__(self, team: Team, *args: Any, **kwargs: Any) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:

        embed = self.team.embed(
            title="Practices.",
            description=f"This team has had **{len(self.team.practices)}** practices in total.",
        )

        # Get the average number of members per practice
        # Get the average total time in a practice.
        average_number_of_members = sum(len(p.members) for p in self.team.practices) / len(self.team.practices)
        average_time = self.team.get_total_practice_time() / len(self.team.practices)

        embed.add_field(
            name='Average Number of Members', value=f'**{average_number_of_members:.2f}** members.', inline=False
        )

        embed.add_field(
            name='Average Practice Time', value=f'**{human_timedelta(average_time.total_seconds())}** total.', inline=False
        )

        # The total number of practices done "in a row". The longest streak of practices (a streak breaks if there is 8 days without a practice)
        streak = self.team.get_practice_streak()
        embed.add_field(
            name="Longest Practice Streak",
            value=f"**{streak}** practices (8 days without a practice breaks the streak).",
            inline=False,
        )

        ranked_members = self.team.rank_member_practice_times()
        embed.add_field(
            name="Top 5 Practice Times",
            value='\n'.join(
                f'{member.mention}: {human_timedelta(time.total_seconds())}' for (member, time) in ranked_members[:5]
            ),
            inline=False,
        )

        absent_members = self.team.rank_member_absences()
        embed.add_field(
            name="Top 5 Absences",
            value='\n'.join(f'{member.mention}: {absences}' for (member, absences) in absent_members[:5]),
            inline=False,
        )

        return embed

    async def _manage_practice_after(self, select: discord.ui.Select[Self], interaction: discord.Interaction) -> None:
        practice_id = int(select.values[0])
        practice = discord.utils.get(self.team.practices, id=practice_id)
        if not practice:
            await interaction.response.edit_message(view=self, embed=self.embed)
            return await interaction.followup.send("That practice doesn't exist anymore.", ephemeral=True)

        view = self.create_child(TeamPracticeView, practice)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label="Manage Practice")
    @default_button_doc_string
    async def manage_practice(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage a specific practice."""
        # A strftime string to turn a datetime into "Month Day, Hour:Minute AM/PM"
        date_format = '%B %d, %I:%M %p'

        options: List[discord.SelectOption] = []
        for practice in self.team.practices[:20]:
            # Practice.ended_at is in UTC, we need to convert it to EST to display it properly.
            # We also need to convert it to a datetime object to use strftime.
            ended_at = practice.ended_at and practice.ended_at.astimezone(tz=EST).strftime(date_format) or 'In Progress...'
            options.append(discord.SelectOption(label=ended_at, value=str(practice.id)))

        select: discord.ui.Select[Self] = discord.ui.Select(
            options=options,
            placeholder='Select a practice to manage...',
        )

        AutoRemoveSelect(
            item=select,
            parent=self,
            callback=self._manage_practice_after,
        )
        return await interaction.response.edit_message(view=self)


class TeamView(BaseView):
    """The main Team View to edit a team."""

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.team.embed(
            title=self.team.display_name,
            description=self.team.description or 'Team has no description.',
        )

        embed.add_field(
            name='Members',
            value=", ".join([m.mention for m in self.team.team_members.values() if m.is_sub is False])
            or "Team has no members.",
            inline=False,
        )
        embed.add_field(
            name='Subs',
            value=", ".join([m.mention for m in self.team.team_members.values() if m.is_sub])
            or "Team has no dedicated subs.",
            inline=False,
        )

        embed.add_field(
            name='Captains',
            value=", ".join(r.mention for r in self.team.captain_roles) or "Team has no captains.",
            inline=False,
        )

        embed.add_field(
            name='Channels',
            value=", ".join(c.mention for c in [self.team.text_channel, self.team.voice_channel, *self.team.extra_channels]),
            inline=False,
        )

        embed.set_footer(text=f'Team ID: {self.team.id}')
        return embed

    async def _delete_team_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        value = modal.children[0].value

        if value.lower() != 'delete':
            return await interaction.response.send_message('Aborted as `delete` was not typed.', ephemeral=True)

        await self.team.delete()
        return await interaction.response.edit_message(content='This team has been deleted.', view=None, embed=None)

    @discord.ui.button(label='Customization')
    @default_button_doc_string
    async def customization(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches the customization view for this team to rename it, change description, etc."""
        view = self.create_child(TeamNamingView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Channels')
    @default_button_doc_string
    async def channels(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s extra channels."""
        view = self.create_child(TeamChannelsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Scrims')
    @default_button_doc_string
    async def scrims(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s scrims."""
        view = self.create_child(TeamScrimsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Members')
    @default_button_doc_string
    async def members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s members."""
        view = self.create_child(TeamMembersView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Captains')
    @default_button_doc_string
    async def captains(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s captains."""
        view = self.create_child(TeamCaptainsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Practices')
    @default_button_doc_string
    async def practices(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s practices."""
        view = self.create_child(TeamPracticesView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Delete Team', style=discord.ButtonStyle.danger)
    @default_button_doc_string
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Delete this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, after=self._delete_team_after, title='Delete Team?'
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Delete Team Confirmation',
                placeholder='Type "DELETE" to confirm...',
                max_length=6,
            )
        )
        return await interaction.response.send_modal(modal)
