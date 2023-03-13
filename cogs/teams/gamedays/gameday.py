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
import enum
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from bot import FuryBot
    from ..team import Team

__all__: Tuple[str, ...] = (
    'GamedayConfig',
    'Weekday',
)


class Weekday(enum.Enum):
    monday = 1
    tuesday = 2
    wednesday = 3
    thursday = 4
    friday = 5
    saturday = 6
    sunday = 7


class GamedayConfig:
    """Represents the gameday configuration for a given team. Every team
    has a gameday configuration, which is used to determine when a team should
    be playing together for their e-sports games.
    
    bot: FuryBot
        The bot instance.
    team: Team
        The team instance.
    id: int
        The ID of the gameday configuration.
    weekday: int
        The day of the week this game is played on.
    game_time: datetime.time
        The time of day this game is played at.
    members_on_team: int
        The number of members that can be on a given team. For example,
        for Rocket League it is 3.
    total_rounds_per_gameday: int
        The total number of rounds that are played in a given gameday.
    best_of: int
        Represents the best of X rounds that are played in a given gameday. So for example,
        if best_of is 3, then the team that wins 2 rounds first wins the gameday.
    """
    def __init__(
        self, 
        /,
        *,
        bot: FuryBot, 
        team: Team, 
        id: int, 
        weekday: int,
        game_time: datetime.time,
        members_on_team: int,
        total_rounds_per_gameday: int,
        best_of: int,
    ) -> None:
        self.bot: FuryBot = bot
        self.team: Team = team
        self.id: int = id
        
        self.weekday: Weekday = Weekday(weekday)
        self.game_time: datetime.time = game_time
        
        self.members_on_team: int = members_on_team
        self.total_rounds_per_gameday: int = total_rounds_per_gameday
        self.best_of: int = best_of
