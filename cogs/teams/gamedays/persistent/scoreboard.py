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
from typing_extensions import Self

import discord
from typing import TYPE_CHECKING, Optional

from utils import AfterModal

if TYPE_CHECKING:
    from ..gameday import Gameday
    from bot import FuryBot


class ScoreboardPanel(discord.ui.View):
    def __init__(self, gameday: Gameday) -> None:
        super().__init__(timeout=None)
        self.gameday: Gameday = gameday
        self.bot: FuryBot = self.gameday.bot

    @property
    def gameday_ended_embed(self) -> discord.Embed:
        embed = self.gameday.team.embed(title=f'Gameday Ended')
        embed.add_field(name=f'Final Score', value=f'**Wins**: {self.gameday.wins}\n**Losses**: {self.gameday.losses}')

        self.gameday.inject_metadata_into_embed(embed)

        return embed

    @property
    def embed(self) -> discord.Embed:
        if not self.gameday.ongoing:
            return self.gameday_ended_embed

        embed = self.gameday.team.embed(title=f'Ongoing Gameday')
        embed.add_field(name='Score', value=f'**Wins**: {self.gameday.wins}\n**Losses**: {self.gameday.losses}')
        embed.set_footer(text=f'Use "/gameday upload" command to upload images of wins and losses to this gameday.')

        self.gameday.inject_metadata_into_embed(embed)
        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        team_member = self.gameday.team.get_member(interaction.user.id)
        if team_member is None:
            return await interaction.response.send_message(
                f'You are not on this team, you can not use this scoreboard panel!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Add Loss', style=discord.ButtonStyle.red, custom_id='add_loss')
    async def add_loss(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self], /
    ) -> Optional[discord.InteractionMessage]:
        await interaction.response.defer()

        await self.gameday.edit(losses=self.gameday.losses + 1)

        if self.gameday.has_won():
            return await self.gameday.end()

        return await interaction.edit_original_response(embed=self.embed)

    @discord.ui.button(label='Add Win', style=discord.ButtonStyle.green, custom_id='add_win')
    async def add_win(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self], /
    ) -> Optional[discord.InteractionMessage]:
        await interaction.response.defer()

        await self.gameday.edit(wins=self.gameday.wins + 1)

        if self.gameday.has_lost():
            return await self.gameday.end()

        return await interaction.edit_original_response(embed=self.embed)

    async def _help_after(
        self, interaction: discord.Interaction[FuryBot], query_input: discord.ui.TextInput[AfterModal]
    ) -> None:
        await interaction.response.defer()

        embed = self.bot.Embed(
            title=f'Assistance Requested by {interaction.user.display_name}',
            description=query_input.value,
            author=interaction.user,
        )
        await interaction.followup.send(
            embed=embed,
            content=', '.join([r.mention for r in self.gameday.team.captain_roles]),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    @discord.ui.button(label='I need help!', style=discord.ButtonStyle.blurple, custom_id='help')
    async def _help(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self], /) -> None:
        modal = AfterModal(
            self.bot,
            self._help_after,
            discord.ui.TextInput(
                label='What do you need help with?',
                style=discord.TextStyle.long,
                placeholder='Enter what you need help with here...',
                max_length=2000,
            ),
            title='Get Help',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)
