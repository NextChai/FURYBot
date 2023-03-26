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
import re
from typing import TYPE_CHECKING, List, Any, Union

import discord
from typing_extensions import Self, Unpack

from utils.ui.select import UserSelect

from .gameday import Weekday

from utils import default_button_doc_string, BaseView, BaseViewKwargs, AfterModal, MultiSelector

if TYPE_CHECKING:
    from .gameday import GamedayBucket, Gameday, GamedayMember
    from bot import FuryBot


class SelectGameday(MultiSelector['GamedayBucketPanel', Gameday]):
    def __init__(self, *, parent: GamedayBucketPanel) -> None:
        super().__init__(
            parent=parent,
            items=list(parent.bucket.get_gamedays().values()),
            per_page=5,
            modal_title='Choose Gameday',
            modal_item=discord.ui.TextInput(
                label='Enter Gameday ID',
                placeholder='Enter the Gameday ID you selected from the embed.',
            ),
        )

    def create_embed(self, gamedays: List[Gameday]) -> discord.Embed:
        embed = self.parent.bucket.team.embed(
            title=f'Select A Gameday',
            description='Use the "Choose Gameday" button to type in the ID of the gameday you want to manage.',
        )

        now = discord.utils.utcnow()
        for gameday in gamedays:
            metadata: List[str] = [f'`ID`: {gameday.id}']

            verbage = 'Starts At' if gameday.started_at > now else 'Started At'
            metadata.append(
                f'`{verbage}`: {discord.utils.format_dt(gameday.started_at, "F")} ({discord.utils.format_dt(gameday.started_at, "R")})'
            )

            if gameday.ended_at is not None:
                metadata.append(
                    f'`Ended At`: {discord.utils.format_dt(gameday.ended_at, "F")} ({discord.utils.format_dt(gameday.ended_at, "R")})'
                )
            else:
                metadata.append('`Status`: Gameday has not ended.')

            # Add some info about the members playing
            members = gameday.get_members()
            mentions: List[str] = []
            for member in members.values():
                if member.is_attending:
                    mentions.append(member.mention)
                else:
                    mentions.append(f'~~{member.mention}~~')

            if mentions:
                metadata.append(f'`Members`: {", ".join(mentions)}')

            embed.add_field(name=f'Gameday {gameday.id}', value='\n'.join(metadata), inline=False)

        return embed

    def hash_item(self, gameday: Gameday) -> str:
        return str(gameday.id)

    async def on_item_chosen(self, interaction: discord.Interaction[FuryBot], item: Gameday) -> Any:
        view = self.parent.create_child(GamedayPanel, gameday=item)
        return await interaction.response.edit_message(view=view, embed=view.embed)


class GamedayMemberPanel(BaseView):
    """Represents the management panel for a given gameday member.

    Parameters
    Attributes
    ----------
    member: :class:`GamedayMember`
        The member you want to edit and manage.
    """

    def __init__(self, member: GamedayMember, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.member: GamedayMember = member

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing this panel."""
        ...

    @discord.ui.button(label='Toggle Is Temporary Sub')
    @default_button_doc_string
    async def toggle_is_temporary_sub(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """A button to toggle whether this member is a temporary sub or not."""
        ...

    @discord.ui.button(label='Edit Reason')
    @default_button_doc_string
    async def edit_reason(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to edit the reason for this member not coming to this gameday."""
        ...

    @discord.ui.button(label='Remove Member From Gameday')
    @default_button_doc_string
    async def remove_member_from_gameday(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """A button to remove this member from the gameday."""
        ...


class GamedayPanel(BaseView):
    """Represents the management panel for a given gameday.

    Parameters
    Attributes
    ----------
    gameday: :class:`Gameday`
        The gameday you want to edit and manage.
    """

    def __init__(self, gameday: Gameday, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.gameday: Gameday = gameday

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing this panel."""
        team = self.gameday.team
        embed = team.embed(
            title=f'{discord.utils.format_dt(self.gameday.started_at, "F")} Gameday',
            description=f'Use the buttons below to manage this gameday.',
        )

        if self.gameday.ended_at is not None:
            embed.add_field(
                name='Ended At',
                value=discord.utils.format_dt(self.gameday.ended_at, "F"),
                inline=False,
            )
        else:
            # If we're past the start time of this gameday then it's in progress
            now = discord.utils.utcnow()
            if now > self.gameday.started_at:
                embed.add_field(
                    name='In Progress',
                    value=f'We are past the start time and this gameday has no set end time so '
                    'it is currently in progress.',
                    inline=False,
                )

        embed.add_field(
            name='Score',
            value=f'**{team.display_name}**: {self.gameday.wins}\n**Other Team**: {self.gameday.losses}',
            inline=False,
        )

        self.gameday.inject_metadata_into_embed(embed)

        return embed

    async def _manage_memnber_after(
        self, interaction: discord.Interaction[FuryBot], users: List[Union[discord.Member, discord.User]]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        member = users[0]
        assert isinstance(member, discord.Member)

        gameday_member = self.gameday.get_member(member.id)
        if gameday_member is None:
            await interaction.followup.send(f'{member.mention} is not involved in this gameday.', ephemeral=True)
            return await interaction.edit_original_response(view=self, embed=self.embed)

        view = self.create_child(GamedayMemberPanel, member=gameday_member)
        return await interaction.edit_original_response(view=view, embed=view.embed)

    @discord.ui.button(label='Manage Member')
    @default_button_doc_string
    async def manage_members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a view that manages a member of this gameday."""
        UserSelect(self._manage_memnber_after, self)

    async def _change_score_after(
        self,
        interaction: discord.Interaction[FuryBot],
        wins_input: discord.ui.TextInput[AfterModal],
        losses_input: discord.ui.TextInput[AfterModal],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        wins = wins_input.value
        losses = losses_input.value

        if wins and not wins.isdigit():
            await interaction.followup.send(f'The wins input must be a number, not {wins!r}.', ephemeral=True)
            return await interaction.edit_original_response(view=self, embed=self.embed)

        if losses and not losses.isdigit():
            await interaction.followup.send(f'The losses input must be a number, not {losses!r}.', ephemeral=True)
            return await interaction.edit_original_response(view=self, embed=self.embed)

        await self.gameday.edit(
            wins=int(wins) if wins else discord.utils.MISSING,
            losses=int(losses) if losses else discord.utils.MISSING,
        )

        # TODO: Need to update the embed here for the current scoreboard
        raise NotImplementedError

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Change Score')
    @default_button_doc_string
    async def change_score(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a model that changes the score of this gameday."""
        modal = AfterModal(
            self.bot,
            self._change_score_after,
            discord.ui.TextInput(label=f'Wins', placeholder='Enter the number of wins to set the score to.'),
            discord.ui.TextInput(label='Losses', placeholder='Enter the number of losses to set the score to.'),
            timeout=None,
            title=f'Change Game Score',
        )
        return await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Start Time')
    @default_button_doc_string
    async def change_start_time(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a model that changes the start time of this gameday."""
        ...

    @discord.ui.button(label='Change End Time')
    @default_button_doc_string
    async def change_end_time(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a model that changes the end time of this gameday."""
        ...


class GamedayBucketPanel(BaseView):
    """Represents the view panel for a given gameday bucket. This will allow the user to edit
    it's settings and view it's current settings.

    Parameters
    Attributes
    ----------
    bucket: :class:`GamedayBucket`
        The bucket that this panel is for.
    """

    def __init__(self, bucket: GamedayBucket, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.bucket = bucket

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing this panel."""
        team = self.bucket.team

        embed = team.embed(
            title=f'{team.display_name} Gameday Bucket Panel',
            description=f'Use the buttons below to manage this team\'s gameday bucket.',
        )
        embed.add_field(
            name='Total Gamedays',
            value=f'I see **{len(self.bucket.get_gamedays())}** gamedays in this bucket.',
            inline=False,
        )

        embed.add_field(
            name='Gameday Scheduled For',
            value=f'Every Gameday is scheduled for {self.bucket.weekday.name} at {self.bucket.game_time.strftime("%I:%M.%S %p")}',
            inline=False,
        )

        embed.add_field(
            name='Team Size',
            value=self.bucket.members_on_team,
        )
        embed.add_field(
            name='Best Of',
            value=f'{self.bucket.best_of} games',
        )
        embed.add_field(
            name='Automatic Sub Finding',
            value=f'Automatic Sub Finding is {"enabled" if self.bucket.automatic_sub_finding else "disabled"}.',
        )

        return embed

    @discord.ui.button(label='Manage A Gameday', style=discord.ButtonStyle.primary)
    async def manage_a_gameday(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a view that manages all gamedays in this bucket."""
        selector = SelectGameday(parent=self)
        await selector.launch(interaction)

    @discord.ui.button(label='Toggle Automatic Sub Finding')
    @default_button_doc_string
    async def toggle_automatic_sub_finding(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Toggles this bucket's automatic sub finding."""
        await interaction.response.defer()

        await self.bucket.edit(
            automatic_sub_finding=not self.bucket.automatic_sub_finding,
        )

        return await interaction.edit_original_response(view=self, embed=self.embed)

    async def _set_team_size_after(
        self, interaction: discord.Interaction[FuryBot], size_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        try:
            size = int(size_input.value)
        except ValueError:
            await interaction.followup.send('This is not a valid number. Please try again.', ephemeral=True)
            return await interaction.edit_original_response(view=self, embed=self.embed)

        await self.bucket.edit(members_on_team=size)

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Set Team Size')
    @default_button_doc_string
    async def set_team_size(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Sets this bucket's team size."""
        modal = AfterModal(
            self.bot,
            self._set_team_size_after,
            discord.ui.TextInput(label='Enter Team Size', placeholder='Enter the new size of the team on game days.'),
            title='Set New Team Size',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)

    async def _set_best_of_after(
        self, interaction: discord.Interaction[FuryBot], best_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        try:
            best_of = int(best_input.value)
        except ValueError:
            await interaction.followup.send('This is not a valid number. Please try again.', ephemeral=True)
            return await interaction.edit_original_response(view=self, embed=self.embed)

        await self.bucket.edit(best_of=best_of)

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Set Best Of')
    @default_button_doc_string
    async def set_best_of(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Sets this bucket's best of."""
        modal = AfterModal(
            self.bot,
            self._set_team_size_after,
            discord.ui.TextInput(label='Enter Best Of', placeholder='Enter the new best for game days.'),
            title='Set New Best Of',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)

    async def _change_time_and_date_after(
        self,
        interaction: discord.Interaction[FuryBot],
        weekday_time_input: discord.ui.TextInput[AfterModal],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        # The weekday_time_input is a string of: Weekday Hour:Minute AM/PM
        # We need to parse this with regex then convert it to a Weekday / datetime.time object
        # Note that AM/PM is optional, so we will default to PM if it's not there
        weekday_time_regex = re.compile(
            r'(?P<weekday>\w+)(?:\s+)(?P<hour>[0-9]{1,})\:(?P<minute>[0-9]+)(?:\s+)?(?P<am_pm>AM|PM)?', re.IGNORECASE
        )

        # Let's try and find a match
        match = weekday_time_regex.match(weekday_time_input.value.lower())
        if not match:
            await interaction.followup.send(
                'This is not a valid time and date. An example would be `Wednesday 4:00 PM`. Feel free to try again.',
                ephemeral=True,
            )
            return await interaction.edit_original_response(view=self, embed=self.embed)

        weekday, hour, minute, maybe_am_pm = match.groups()

        try:
            weekday = Weekday[weekday.lower()]
        except KeyError:
            await interaction.followup.send(
                'This is not a valid weekday. An example would be `Tuesday 5:00 PM`. Feel free to try again.',
                ephemeral=True,
            )
            return await interaction.edit_original_response(view=self, embed=self.embed)

        # Let's convert the hour and minute to integers
        hour = int(hour)
        minute = int(minute)
        am_pm = maybe_am_pm or 'PM'

        if am_pm == 'PM':
            # Add 12 to the hour if it's PM to move into the 24 hour clock
            hour += 12

        try:
            time = datetime.time(hour=hour, minute=minute)
        except ValueError as exc:
            await interaction.followup.send(
                f'You did not enter a valid time. {str(exc).capitalize()}. Feel free to try again.',
                ephemeral=True,
            )
            return await interaction.edit_original_response(view=self, embed=self.embed)

        await self.bucket.edit(weekday=weekday, game_time=time)

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Change Gameday Time and Date')
    @default_button_doc_string
    async def change_gameday_time_and_date(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Changes this bucket's gameday time and date."""
        modal = AfterModal(
            self.bot,
            self._change_time_and_date_after,
            discord.ui.TextInput(
                label='Enter Time and Date.',
                placeholder='Format: Weekday Hour:Minute AM/PM. Example: Wednesday 4:00 PM',
                required=True,
            ),
            title='Change Gameday Time and Date',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)
