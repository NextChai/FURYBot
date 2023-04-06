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

import logging
from typing import TYPE_CHECKING, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, human_join

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('GamedayEventListener', 'GamedayCommands')

_log = logging.getLogger(__name__)


class GamedayEventListener(BaseCog):
    @commands.Cog.listener('on_gameday_start_timer_complete')
    async def on_gameday_start(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        ...

    @commands.Cog.listener('on_gameday_voting_start_timer_complete')
    async def on_gameday_voting_start(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            _log.debug('Guild %s not found.', guild_id)
            return

        team = self.bot.get_team(team_id, guild_id)
        if team is None:
            _log.debug('Team %s not found.', team_id)
            return

        bucket = team.get_gameday_bucket()
        if bucket is None:
            _log.debug('Gameday bucket not found.')
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug('Gameday %s not found.', gameday_id)
            return

        # We need to send the view to the channel!
        view = self.bot.attendance_voting_view
        if view is None:
            _log.debug('Attendance voting view not found.')
            return

        embed = view.create_embed(gameday)
        channel = team.text_channel

        team_member_mentions = human_join(
            (m.mention for m in team.main_roster), additional='please confirm your attendance for the upcoming gameday.'
        )

        message = await channel.send(embed=embed, view=view, content=team_member_mentions)

        async with self.bot.safe_connection() as connection:
            await gameday.edit(
                connection=connection,
                voting_message_id=message.id,
            )

    @commands.Cog.listener('on_gameday_voting_end_timer_complete')
    async def on_gameday_voting_end(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        ...


class GamedayCommands(BaseCog):

    gameday = app_commands.Group(name='gameday', description='Commands related to gamedays.')

    @gameday.command(name='upload')
    async def gameday_upload(self, interaction: discord.Interaction[FuryBot], image: discord.Attachment) -> None:
        ...
