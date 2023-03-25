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

from typing import TYPE_CHECKING

import discord
from typing_extensions import Self, Unpack

from utils import default_button_doc_string, BaseView, BaseViewKwargs

if TYPE_CHECKING:
    from .gameday import GamedayBucket, Gameday, GamedayMember
    from bot import FuryBot


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

    @discord.ui.button(label='Manage Member')
    @default_button_doc_string
    async def manage_members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a view that manages a member of this gameday."""
        ...

    @discord.ui.button(label='Change Score')
    @default_button_doc_string
    async def change_score(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a model that changes the score of this gameday."""
        ...

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

    @discord.ui.button(label='Toggle Automatic Sub Finding')
    @default_button_doc_string
    async def toggle_automatic_sub_finding(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Toggles this bucket's automatic sub finding."""
        ...

    @discord.ui.button(label='Set Team Size')
    @default_button_doc_string
    async def set_team_size(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Sets this bucket's team size."""
        ...

    @discord.ui.button(label='Set Best Of')
    @default_button_doc_string
    async def set_best_of(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Sets this bucket's best of."""
        ...

    @discord.ui.button(label='Change Gameday Time and Date')
    @default_button_doc_string
    async def change_gameday_time_and_date(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Changes this bucket's gameday time and date."""
        ...
