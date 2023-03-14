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
from utils import BaseCog

from discord.ext import commands

from .persistent.attendance import GamedayAttendanceView

_log = logging.getLogger(__name__)


class GamedayEventListener(BaseCog):
    """Listens for gameday events to be dispatched from the timer manager.

    This will handle the following timer dispatching events and do the following:

    - Notification a day in advance to a gameday at 11am EST. This will launch the yes
    or no attending persistent panel. This will launch another timer that expires 5 hours
    from now to determine the results of the poll.

    - Handles the 5 hour timer that expires to determine the results of the poll. If
    auto sub finding is enabled, this will start searching for subs. If it's disabled,
    it will alert the captain(s) and end the flow.

    - 4 hours before the given gameday, this will send a reminder to the players and subs
    about the upcoming game. If the team has not been filled for the given gameday then
    a captain will be alerted that they need to find subs.

    - At the scheduled gameday time, this will send the scoreboard to the team channel.
    """

    @commands.Cog.listener('on_advance_gameday_notification_timer_complete')
    async def on_advance_gameday_notification_timer_complete(
        self, guild_id: int, team_id: int, gameday_bucket_id: int, gameday_id: int
    ) -> None:
        """|coro|

        The timer listener for the advance gameday notificatrionm timer. This is the timer that launches
        11am EST the day before the gameday and starts launching the persistent panel for the yes or no.
        """
        bucket = self.bot.get_gameday_bucket(guild_id, team_id, gameday_bucket_id)
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

        # Need to send to team's text channel here.
        raise NotImplemented
