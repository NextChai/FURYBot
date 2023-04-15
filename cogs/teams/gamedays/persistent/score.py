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

from utils import AfterModal

from ..gameday import GamedayScoreReport

if TYPE_CHECKING:
    from bot import FuryBot

    from ..gameday import Gameday


class ScoreReportView(discord.ui.View):
    async def create_sender_inforamtion(self, gameday: Gameday) -> Tuple[discord.Embed, List[discord.File]]:
        ...

    async def _find_gameday_from_interaction(self, interaction: discord.Interaction[FuryBot]) -> Optional[Gameday]:
        await interaction.response.defer()

        bot = interaction.client

        assert interaction.guild_id
        assert interaction.channel_id

        team = bot.get_team_from_channel(interaction.channel_id, interaction.guild_id)
        if team is None:
            await interaction.followup.send('I was unable to locate a team for this channel.', ephemeral=True)
            return

        ongoing_gameday = team.ongoing_gameday
        if ongoing_gameday is None:
            await interaction.followup.send('There is no ongoing gameday for this team.', ephemeral=True)
            return

        return ongoing_gameday

    async def _report_score_after(
        self, interaction: discord.Interaction[FuryBot], score_input: discord.ui.TextInput[AfterModal], *, gameday: Gameday
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        async with interaction.client.safe_connection() as connection:
            await GamedayScoreReport.create(
                interaction.client,
                connection=connection,
                guild_id=gameday.guild_id,
                team_id=gameday.team_id,
                bucket_id=gameday.bucket_id,
                gameday_id=gameday.id,
                text=score_input.value,
                reported_by_id=interaction.user.id,
                reported_at=interaction.created_at,
            )

        await interaction.followup.send('Your score report has been successfully submitted.', ephemeral=True)

        embed, attachments = await self.create_sender_inforamtion(gameday)
        return await interaction.edit_original_response(embed=embed, attachments=attachments)

    @discord.ui.button(label='Report Score', style=discord.ButtonStyle.green, custom_id='score-report-view:report-score')
    async def report_score(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = await self._find_gameday_from_interaction(interaction)
        if gameday is None:
            return

        modal = AfterModal(
            interaction.client,
            self._report_score_after,
            discord.ui.TextInput(
                label='Enter The Score',
                style=discord.TextStyle.long,
                placeholder='Enter the score of the game in any format you\'d like, the bot will '
                'not try to parse it, it\'s up for this team\'s captain to do that.',
            ),
            title='Enter Gameday Score',
            timeout=None,
            gameday=gameday,
        )
        return await interaction.response.send_modal(modal)

    @discord.ui.button(label='Mark Gameday as Complete', custom_id='score-report-view:mark-complete')
    async def mark_complete(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        gameday = await self._find_gameday_from_interaction(interaction)
        if gameday is None:
            return

        async with interaction.client.safe_connection() as connection:
            await gameday.edit(connection=connection, ended_at=interaction.created_at)

        embed, attachments = await self.create_sender_inforamtion(gameday)
        await interaction.edit_original_response(view=None, embed=embed, attachments=attachments)
