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

from typing import TYPE_CHECKING, List, Optional, Tuple

import discord
from typing_extensions import Self

from utils import AfterModal, human_join, human_timestamp

from ..gameday import GamedayScoreReport, get_next_gameday_time, Gameday

if TYPE_CHECKING:
    from bot import FuryBot


class ScoreReportView(discord.ui.View):
    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> Optional[bool]:
        assert interaction.guild_id
        assert interaction.channel_id

        team = interaction.client.get_team_from_channel(interaction.channel_id, interaction.guild_id)
        if team is None:
            return await interaction.response.send_message('I was unable to locate a team for this channel.', ephemeral=True)

        team_member = team.get_member(interaction.user.id)
        if team_member is None:
            return await interaction.response.send_message('You are not a member of this team.', ephemeral=True)

        return True

    async def create_sender_information(self, gameday: Gameday) -> Tuple[discord.Embed, List[discord.File]]:
        team = gameday.team
        if team is None:
            raise ValueError('Gameday has no team.')

        report_texts = '\n'.join(
            f'- {report.text} (Reported by <@{report.reported_by_id}>)' for report in gameday.score_reports.values()
        )

        description = f'Below shows all the score reports for the current gameday. This gameday started at {human_timestamp(gameday.starts_at)}'
        if gameday.has_ended:
            assert gameday.ended_at
            description += f' and ended at {human_timestamp(gameday.ended_at)}.'
        else:
            description += f' and is currently in progress.'

        embed = team.embed(
            title=f'Gameday Score Report',
            description=f'{description}\n\n{report_texts}',
        )

        file = await gameday.merge_images()
        if file is not None:
            embed.set_image(url=f'attachment://{file.filename}')

        attachments = [file] if file is not None else []
        return embed, attachments

    async def _find_gameday_from_interaction(
        self, interaction: discord.Interaction[FuryBot], defer: bool = True
    ) -> Optional[Gameday]:
        if defer is True:
            await interaction.response.defer()

        sender = (
            functools.partial(interaction.followup.send, ephemeral=True)
            if interaction.response.is_done()
            else functools.partial(interaction.response.send_message, ephemeral=True)
        )

        bot = interaction.client

        assert interaction.guild_id
        assert interaction.channel_id

        team = bot.get_team_from_channel(interaction.channel_id, interaction.guild_id)
        if team is None:
            await sender(content='I was unable to locate a team for this channel.')
            return

        ongoing_gameday = discord.utils.find(
            lambda g: g.score_message_id is not None
            and g.score_message_id == (interaction.message and interaction.message.id),
            team.ongoing_gamedays,
        )
        if not ongoing_gameday:
            await sender(content='There is no ongoing gameday for this team.')
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

        embed, attachments = await self.create_sender_information(gameday)
        return await interaction.edit_original_response(embed=embed, attachments=attachments)

    @discord.ui.button(label='Report Score', style=discord.ButtonStyle.green, custom_id='score-report-view:report-score')
    async def report_score(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        gameday = await self._find_gameday_from_interaction(interaction, defer=False)
        if gameday is None:
            return

        modal = AfterModal(
            interaction.client,
            self._report_score_after,
            discord.ui.TextInput(
                label='Enter The Score',
                style=discord.TextStyle.long,
                placeholder='Enter the score of the game in any format you\'d like.',
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

        team = gameday.team
        if team is None:
            raise ValueError('Gameday has no team.')

        async with interaction.client.safe_connection() as connection:
            await gameday.edit(connection=connection, ended_at=interaction.created_at)

            # Let's create next week's gameday.
            gameday_time = gameday.time
            if gameday_time is not None:  # Could have been deleted, so we need to check.
                next_gameday_time = get_next_gameday_time(weekday=gameday_time.weekday, game_time=gameday_time.starts_at)
                await Gameday.create(
                    bot=interaction.client,
                    connection=connection,
                    guild_id=gameday.guild_id,
                    team_id=gameday.team_id,
                    bucket_id=gameday.bucket_id,
                    gameday_time_id=gameday_time.id,
                    starts_at=next_gameday_time,
                )

        embed, attachments = await self.create_sender_information(gameday)

        captain_mentions = (r.mention for r in team.captain_roles)
        content = (
            human_join(captain_mentions, additional='please review the score for this given gameday.')
            if captain_mentions
            else ''
        )

        await interaction.followup.send(
            embed=embed,
            files=attachments,
            content=content,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
