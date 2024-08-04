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

import functools
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import discord
from typing_extensions import Self, Unpack

from utils import (
    AfterModal,
    BaseView,
    BaseViewKwargs,
    SelectOneOfMany,
    TimeTransformer,
    UserSelect,
    default_button_doc_string,
)

from .persistent import AwayConfirm, HomeConfirm

if TYPE_CHECKING:
    from bot import FuryBot

    from ..team import Team
    from .scrim import Scrim, ScrimStatus


__all__: Tuple[str, ...] = ('TeamScrimsPanel', 'ScrimPanel')


class ScrimPanel(BaseView):
    """Represents a view used to manage a scrim.

    Parameters
    Attributes
    ----------
    team: :class:`.Team`
        The team currently being viewed in the view history.
    scrim: :class:`.Scrim`
        The scrim to manage.
    """

    def __init__(self, team: Team, scrim: Scrim, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        self.scrim: Scrim = scrim
        super().__init__(**kwargs)

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
        self, interaction: discord.Interaction[FuryBot], reschedule_input: discord.ui.TextInput[AfterModal]
    ) -> None:
        await interaction.response.defer()

        # Let's try and parse this time
        try:
            transformed = await TimeTransformer('n/a').transform(interaction, reschedule_input.value)
        except Exception as exc:
            await interaction.edit_original_response(embed=self.embed, view=self)
            return await interaction.followup.send(content=str(exc), ephemeral=True)

        assert transformed.dt
        await self.scrim.reschedle(transformed.dt, editor=interaction.user)
        await interaction.edit_original_response(
            content=f'I\'ve rescheduled this scrim for {self.scrim.scheduled_for_formatted()}.'
        )

    @discord.ui.button(label='Reschedule')
    @default_button_doc_string
    async def reschedule_scrim(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Reschedule this scrim to a later date."""
        # If this scrim has already started, we can't reschedule it
        if self.scrim.scheduled_for < interaction.created_at:
            return await interaction.response.send_message(
                'This scrim has already started, you cannot reschedule it.', ephemeral=True
            )

        modal = AfterModal(self.bot, after=self._reschedule_scrim_after)
        modal.add_item(
            discord.ui.TextInput(label='When you want to reschedule this scrim to. For example: Tomorrow at 4pm.')
        )
        await interaction.response.send_modal(modal)

    async def _manage_member_assignment(
        self,
        interaction: discord.Interaction[FuryBot],
        members: List[Union[discord.Member, discord.User]],
        *,
        add_vote: bool = True,
    ) -> None:
        await interaction.response.defer()

        home_team = self.scrim.home_team
        away_team = self.scrim.away_team

        for member in members:
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

    @discord.ui.button(label='Remove Confirmation')
    @default_button_doc_string
    async def remove_confirmation(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Forcefully remove confirmation for a member."""
        UserSelect(after=functools.partial(self._manage_member_assignment, add_vote=False), parent=self)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Add Confirmation')
    @default_button_doc_string
    async def force_add_confirmation(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Forcefully add confirmation for a member."""

        UserSelect(after=functools.partial(self._manage_member_assignment, add_vote=True), parent=self)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Schedule Scrim')
    @default_button_doc_string
    async def force_schedule_scrim(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
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
    async def cancel_scrim(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Force cancel the scrim and remove it from the database."""
        await interaction.response.defer()
        await self.scrim.cancel()

        # Go back to the TeamScrimsView, the parent of this view, and edit the original response.
        # We can't go back in the parent tree because I dont want the user to try and edit
        # a cancelled scrim.
        view = TeamScrimsPanel(self.team, target=self.target)
        await interaction.edit_original_response(embed=view.embed, view=view)


class TeamScrimsPanel(BaseView):
    """A view used to manage a teams scrims, alter times, etc.

    Parameters
    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

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

    async def _manage_a_scrim_callback(self, interaction: discord.Interaction[FuryBot], values: List[str]) -> None:
        scrim = discord.utils.get(self.team.scrims, id=int(values[0]))
        if not scrim:
            # Something really went wrong!
            return await interaction.response.edit_message(embed=self.embed, view=self)

        view = ScrimPanel(self.team, scrim, target=self.target)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Select a Scrim')
    @default_button_doc_string
    async def manage_a_scrim(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Allows the user to select a scrim to manage."""
        if not self.team.scrims:
            return await interaction.response.send_message('This team has no scrims.', ephemeral=True)

        SelectOneOfMany(
            self,
            options=[
                discord.SelectOption(
                    label=scrim.scheduled_for.strftime("%A, %B %d, %Y at %I:%M %p"),
                    value=str(scrim.id),
                )
                for scrim in self.team.scrims
            ],
            placeholder='Select a scrim to manage...',
            after=self._manage_a_scrim_callback,
        )

        # The AutoRemoveSelect automatically removes all children
        # and adds itslef. Once the select has been completed it will
        # add the children back and call the "_manage_a_scrim_callback" callback for us.
        return await interaction.response.edit_message(view=self)
