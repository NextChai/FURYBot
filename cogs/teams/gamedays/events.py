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

import discord
from discord.ext import commands

from utils import BaseCog

from .persistent.attendance import GamedayAttendanceView

_log = logging.getLogger(__name__)


class GamedayEventListener(BaseCog):
    """Listens for gameday events to be dispatched from the timer manager.

    This will handle the following timer dispatching events and do the following:

    - Notification a day in advance to a gameday at 11am EST. This will launch the yes
    or no attending persistent panel.

    - Handles the 5 hour timer that expires to determine the results of the poll. If
    auto sub finding is enabled, this will start searching for subs. If it's disabled,
    it will alert the captain(s) and end the flow.

    - 4 hours before the given gameday, this will send a reminder to the players and subs
    about the upcoming game. If the team has not been filled for the given gameday then
    a captain will be alerted that they need to find subs.

    - At the scheduled gameday time, this will send the scoreboard to the team channel.
    """

    @commands.Cog.listener('on_gameday_start_timer_complete')
    async def on_gameday_start(self, guild_id: int, team_id: int, gameday_bucket_id: int, gameday_id: int) -> None:
        # TODO: Launch the scoreboard
        raise NotImplementedError

    @commands.Cog.listener('on_attendance_voting_start_timer_complete')
    async def on_attendance_voting_start(self, guild_id: int, team_id: int, gameday_bucket_id: int, gameday_id: int) -> None:
        """|coro|

        The timer listener for the advance gameday notificatrionm timer. This is the timer that launches
        11am EST the day before the gameday and starts launching the persistent panel for the yes or no.
        """
        bucket = self.bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            _log.debug(
                'Ignoring bucket to guild %s team %s bucket id %s in advance gameday notification timer complete',
                guild_id,
                team_id,
                gameday_bucket_id,
            )
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug(
                'Gameday %s not found in bucket %s to guild %s in team %s in advance gameday notification timer complete',
                gameday_id,
                gameday_bucket_id,
                guild_id,
                team_id,
            )
            return

        view = GamedayAttendanceView(self.bot, gameday)

        channel = gameday.team.text_channel
        message = await channel.send(embed=view.embed, view=view)

        # Let's edit the gameday to also include the message ID of this notification message
        # so when the 5 hour timeout is reached we can check it.
        await gameday.edit(attendance_voting_message_id=message.id)

    @commands.Cog.listener('on_attendance_voting_end_timer_complete')
    async def on_attendance_voting_end(self, guild_id: int, team_id: int, gameday_bucket_id: int, gameday_id: int) -> None:
        bucket = self.bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            _log.debug(
                'Ignoring bucket to guild %s team %s bucket id %s in advance gameday notification timer complete',
                guild_id,
                team_id,
                gameday_bucket_id,
            )
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug(
                'Gameday %s not found in bucket %s to guild %s in team %s in advance gameday notification timer complete',
                gameday_id,
                gameday_bucket_id,
                guild_id,
                team_id,
            )
            return

        attendance_message_id = gameday.attendance_voting_message_id
        if attendance_message_id is None:
            _log.debug(
                'Unable to end voting as the attendance voting message ID is not set for gameday %s in bucket %s to guild %s in team %s',
                gameday_id,
                gameday_bucket_id,
                guild_id,
                team_id,
            )
            return

        channel = gameday.team.text_channel
        partial_attedance_message = channel.get_partial_message(attendance_message_id)

        # Let's edit it to remove the view and update the embed
        subs_needed = gameday.subs_needed
        embed = gameday.team.embed(
            title=f'Gameday Attendance',
            description=f'**{len(gameday.get_members_attending())}** have marked themselves as attending this gameday. This '
            f'poll has come to an end, which means this gameday will need {subs_needed} sub(s) to be filled.',
        )

        if subs_needed > 0:
            embed.add_field(
                name='Auto Sub Finding',
                value=f'This team needs subs and automatic sub finding is {"enabled" if gameday.bucket.automatic_sub_finding else "disabled"}. '
                'There is no guarantee this team will be filled.',
            )

        gameday.inject_metadata_into_embed(embed)

        await partial_attedance_message.edit(view=None)

        captain_mentions = [r.mention for r in gameday.team.captain_roles]
        await partial_attedance_message.reply(
            content=', '.join(captain_mentions), embed=embed, allowed_mentions=discord.AllowedMentions(roles=True)
        )

        # TODO: Impl automatic sub finding here
        raise NotImplementedError
