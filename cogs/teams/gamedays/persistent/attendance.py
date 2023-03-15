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

from typing import TYPE_CHECKING, Optional, Union
from typing_extensions import Self

import discord

from ..gameday import GamedayMember

if TYPE_CHECKING:
    from bot import FuryBot
    from ..gameday import Gameday


class CannotAttendModal(discord.ui.Modal):
    reason: discord.ui.TextInput[Self] = discord.ui.TextInput(
        label='Reason for Absence',
        custom_id='modal:cannot-attend-reason',
        placeholder='Why can\'t you attend?',
        style=discord.TextStyle.long,
    )

    def __init__(self, parent: GamedayAttendanceView, invoker: Union[discord.User, discord.Member]) -> None:
        super().__init__(timeout=None, title=f'Why can\'t you attend?')
        self.parent: GamedayAttendanceView = parent
        self.invoker: Union[discord.User, discord.Member] = invoker

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        if interaction.user != self.invoker:
            return await interaction.response.send_message(f'This does not belong to you?', ephemeral=True)

        return True

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> discord.InteractionMessage:
        await interaction.response.defer()

        await GamedayMember.create(self.invoker, self.parent.gameday, reason=self.reason.value)

        embed = self.parent.embed
        await interaction.followup.send(f'I\'ve marked you as not attending for this gameday.', ephemeral=True)
        return await interaction.edit_original_response(embed=embed)


class GamedayAttendanceView(discord.ui.View):
    def __init__(self, bot: FuryBot, gameday: Gameday) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = bot
        self.gameday: Gameday = gameday

    @property
    def filled_embed(self) -> discord.Embed:
        team = self.gameday.team
        embed = team.embed(
            title=f'{team.display_name} Gameday Attendance',
            description=f'This team has a gameday coming up on {discord.utils.format_dt(self.gameday.started_at, "F")} ({discord.utils.format_dt(self.gameday.started_at, "R")}). '
            f'This team has been filled with members who have marked themselves as attending, in {discord.utils.format_dt(self.gameday.attendance_voting_end, "R")} this '
            'panel will automatically close and the captains will be notified.',
        )

        embed.add_field(
            name='All Roster Spots Filled',
            value=f'**{len(self.gameday.get_members())} members** have marked themselves as attending, which is '
            f'enough to fill the {self.gameday.bucket.members_on_team} roster spots.',
            inline=False,
        )

        self.gameday.inject_metadata_into_embed(embed)

        return embed

    @property
    def embed(self) -> discord.Embed:
        team = self.gameday.team
        embed = team.embed(
            title=f'{team.display_name} Gameday Attendance',
            description=f'This team has a gameday coming up on {discord.utils.format_dt(self.gameday.started_at, "F")} ({discord.utils.format_dt(self.gameday.started_at, "R")}). '
            'Please use the buttons below to mark yourself as attending or not attending for tomorrows gameday. Note this attendance panel will '
            f'expire in {discord.utils.format_dt(self.gameday.attendance_voting_end, "R")}. After that time, if needed, subs will be found '
            'to fill the roster and you will not be able to mark yourself as attending.',
        )

        self.gameday.inject_metadata_into_embed(embed)

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        # Let's check if this user is on the team or not
        team = self.gameday.team
        team_member = team.get_member(interaction.user.id)

        if team_member is None:
            return await interaction.response.send_message(
                f'You need to be on this team in order to use this panel.', ephemeral=True
            )

        if team_member.is_sub:
            return await interaction.response.send_message(
                f'At this time, this panel is only checking for main roster members on this team. If a sub is needed, you will '
                'be notified.',
                ephemeral=True,
            )

        # Check if this member has already marked themselves as attending or not.
        gameday_member = self.gameday.get_member(team_member.member_id)
        if gameday_member is not None:
            return await interaction.response.send_message(
                f'You have already marked yourself as {"attending" if gameday_member.is_attending else "not attending"} for this gameday.',
                ephemeral=True,
            )

        return True

    @discord.ui.button(label='Can Attend', style=discord.ButtonStyle.green)
    async def can_attend(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        await GamedayMember.create(interaction.user, self.gameday)

        # If we have enough members to fill the entire team, let's close this panel.
        if self.gameday.is_full:
            for child in self.children:
                assert isinstance(child, discord.ui.Button)
                child.disabled = True

            return await interaction.edit_original_response(embed=self.filled_embed, view=self)

        return await interaction.edit_original_response(embed=self.embed)

    @discord.ui.button(label='Cannot Attend', style=discord.ButtonStyle.red)
    async def cannot_attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        return await interaction.response.send_modal(CannotAttendModal(self, interaction.user))
