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

import dataclasses
import datetime
import enum
import math
from typing import TYPE_CHECKING, Dict, List, Mapping, Optional, Tuple, Type, Union

import discord
from typing_extensions import Self

if TYPE_CHECKING:
    from bot import FuryBot, ConnectionType

from utils.bases import Teamable, TeamMemberable

__all__: Tuple[str, ...] = (
    'GamedayBucket',
    'Gameday',
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


@dataclasses.dataclass()
class GamedayMember(TeamMemberable):
    """Represents a member who has confirmed or not confirmed that they will be attending a gameday.

    A temporary sub is one found in a chat, such as a sub-finding channel, that shouldn't remain on the team after the game is over.
    This sub will be auto-removed from the team after 1 hour of the gameday coming to an end.
    """

    bot: FuryBot

    id: int
    member_id: int
    team_id: int
    guild_id: int
    gameday_id: int

    # Determines if the member has confirmed that they will be attending the gameday.
    reason: Optional[str]

    is_temporary_sub: bool = False

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    def _get_member_id(self) -> int:
        return self.member_id

    @classmethod
    async def create(
        cls: Type[Self], user: Union[discord.Member, discord.User], gameday: Gameday, *, is_temporary_sub: bool = False
    ) -> Self:
        bot = gameday.bot
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.gameday_members(gameday_id, team_id, member_id, guild_id, is_temporary_sub) '
                'VALUES($1, $2, $3, $4, $5) '
                'RETURNING *',
                gameday.id,
                gameday.team_id,
                user.id,
                gameday.guild_id,
                is_temporary_sub,
            )
            assert data

        self = cls(bot, **dict(data))
        gameday.add_member(self)

        return self

    @property
    def is_attending(self) -> bool:
        return bool(self.reason)

    async def delete(self) -> None:
        bot = self.bot
        async with bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM teams.gameday_members WHERE id = $1',
                self.id,
            )


class Gameday(Teamable):
    """Represents a gameday for a given team. A gameday is where a team gets together in order to play their e-sports games.

    A gameday is made up of rounds, which are represented by the :class:`Round` class. A gameday is made up of a total number of rounds,
    which is determined by the gameday bucket.

    Gameday Flow
    ------------
        - Members will get a notification a day in advance at 11am EST to remind them they have a gameday coming up. Members will chose yes or no to attending.
        If they chose no then they'll be required to provide a reason for not attending.

            - Once all members have voted, or the team has been filled, the team's captain(s) will be notified. This has a 5 hour timeout.

        - If all team members have voted and the team is not filled, or 5 hours have passed, the bot will spawn one of two responses.

            - If auto sub finding is enabled, the client will make an effort to find a replacement for N members required to fill the team
            using the specified sub role and sub channel. If the team has dedicated subs, the bot will look for those subs first (with a timeout of 3 hours),
            then extend the search to the sub role and sub channel excluding the subs the bot already tried to recruit.

            - If auto sub finding is disabled, the client will notify the team's captain(s) that the team is not filled and that they need to find a replacement.

    - 4 hours before the scheduled gameday, the bot will send a reminder to all members that have agreed to attend the gameday.

        - If the team has not been filled by this point, the bot will notify the team's captain(s) that the team is not filled and
        that they need to find a replacement. This notification to the captain will be regardless of the auto sub finding setting.

    - During the gameday, the bot will send a scoreboard to the team's text-channel. After each round of the gameday, a member of the team
    will be required to update the scoreboard. They can either press the "Win" or "Loss" button on the scoreboard to update it.

        - Optionally, team members can upload an in-game screenshot of each round to have for proof in case of an issue. This will be achieveed
        via the `/gameday upload <attachment: Attachment>` command. **We will encourage members to do this, but it will not be required.**

    - After a winner has been decided, the bot will gather the in-game screenshots, if applicable, and merge them to be sent in the final notification.
    This notification will mention the team's captain(s) that their gameday is over.
    """

    def __init__(
        self,
        /,
        *,
        bot: FuryBot,
        bucket_id: int,
        id: int,
        guild_id: int,
        team_id: int,
        started_at: datetime.datetime,
        wins: int,
        losses: int,
        ended_at: Optional[datetime.datetime] = None,
        members: Dict[int, GamedayMember] = {},
    ) -> None:
        self.bot: FuryBot = bot
        self.id: int = id
        self.guild_id: int = guild_id
        self.team_id: int = team_id
        self.started_at: datetime.datetime = started_at
        self.ended_at: Optional[datetime.datetime] = ended_at
        self.bucket_id: int = bucket_id

        # Wins and losses for the team for the given game.
        self.wins: int = wins
        self.losses: int = losses

        self._members: Dict[int, GamedayMember] = members

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    @classmethod
    async def fetch_members(
        cls: Type[Self], bot: FuryBot, gameday_id: int, *, connection: ConnectionType
    ) -> Dict[int, GamedayMember]:
        data = await connection.fetch(
            'SELECT * FROM teams.gameday_members WHERE gameday_id = $1',
            gameday_id,
        )

        return {row['member_id']: GamedayMember(bot=bot, **dict(row)) for row in data}

    @property
    def subs_needed(self) -> int:
        return self.bucket.members_on_team - len(self.get_members())

    @property
    def bucket(self) -> GamedayBucket:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.id, get=False)

    def add_member(self, member: GamedayMember) -> None:
        self._members[member.member_id] = member

    def remove_member(self, member_id: int) -> None:
        self._members.pop(member_id, None)

    def get_member(self, member_id: int) -> Optional[GamedayMember]:
        return self._members.get(member_id)

    def get_members(self) -> Dict[int, GamedayMember]:
        return self._members

    def get_members_attending(self) -> Dict[int, GamedayMember]:
        return {k: v for k, v in self._members.items() if v.is_attending}


class GamedayBucket(Teamable):
    """Represents the gameday bucket for a given team. Every team
    has a gameday bucket, which is used to determine when a team should
    be playing together for their e-sports games.

    bot: FuryBot
        The bot instance.
    team: Team
        The team instance.
    id: int
        The ID of the gameday bucket.
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
        team_id: int,
        guild_id: int,
        id: int,
        weekday: int,
        game_time: datetime.time,
        members_on_team: int,
        total_rounds_per_gameday: int,
        best_of: int,
        automatic_sub_finding: bool,
    ) -> None:
        self.bot: FuryBot = bot
        self.team_id: int = team_id
        self.guild_id: int = guild_id
        self.id: int = id

        self.weekday: Weekday = Weekday(weekday)
        self.game_time: datetime.time = game_time

        self.members_on_team: int = members_on_team
        self.total_rounds_per_gameday: int = total_rounds_per_gameday
        self.best_of: int = best_of
        self.automatic_sub_finding: bool = automatic_sub_finding

        self._gamedays: Dict[int, Gameday] = {}

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    @classmethod
    async def fetch_gamedays(
        cls: Type[Self], bot: FuryBot, gameday_bucket_id: int, *, connection: ConnectionType
    ) -> List[Gameday]:
        gamedays: List[Gameday] = []
        data = await connection.fetch('SELECT * FROM teams.gamedays WHERE bucket_id = $1', gameday_bucket_id)

        for row in data:
            members = await Gameday.fetch_members(bot=bot, gameday_id=row['id'], connection=connection)
            gameday = Gameday(bot=bot, members=members, **dict(row))
            gamedays.append(gameday)

        return gamedays

    def get_gamedays(self) -> Mapping[int, Gameday]:
        return self._gamedays

    def get_gameday(self, gameday_id: int) -> Optional[Gameday]:
        return self._gamedays.get(gameday_id)

    def add_gameday(self, gameday: Gameday) -> None:
        self._gamedays[gameday.id] = gameday

    def remove_gameday(self, gameday_id: int) -> None:
        self._gamedays.pop(gameday_id, None)

    @property
    def wins_needed(self) -> int:
        return math.ceil(self.best_of / 2)
