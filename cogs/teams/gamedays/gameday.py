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

from utils import QueryBuilder, image_from_urls, image_to_file
from .persistent.scoreboard import ScoreboardPanel

if TYPE_CHECKING:
    from bot import FuryBot, ConnectionType

from utils.bases import Teamable, TeamMemberable

__all__: Tuple[str, ...] = (
    'GamedayBucket',
    'Gameday',
    'Weekday',
)

MISSING = discord.utils.MISSING


def _get_attendance_voting_start_time(gameday_starts_at: datetime.datetime) -> datetime.datetime:
    # Let's go to midnight (12:00am) then subtract 9 hours to get to 11am EST time.
    midnight = gameday_starts_at.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - datetime.timedelta(hours=9)


def _get_attendance_voting_end_time(gameday_starts_at: datetime.datetime) -> datetime.datetime:
    # Let's go to midnight (12:00am) then subtract 4 hours to get to 4pm EST time.
    return _get_attendance_voting_start_time(gameday_starts_at) + datetime.timedelta(hours=5)


def _get_next_gameday_time(now: datetime.datetime, /, *, weekday: Weekday, game_time: datetime.time) -> datetime.datetime:
    # Calculate the next occurrence of the given weekday
    days_until_gameday = (weekday.value - now.weekday() - 1) % 7
    next_gameday = now + datetime.timedelta(days=days_until_gameday)

    next_gameday = next_gameday.replace(
        hour=game_time.hour, minute=game_time.minute, second=game_time.second, microsecond=game_time.microsecond
    )

    return next_gameday


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

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.member_id == __o.member_id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def __hash__(self) -> int:
        return hash(self.member_id)

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
        cls: Type[Self],
        user: Union[discord.Member, discord.User],
        gameday: Gameday,
        *,
        is_temporary_sub: bool = False,
        reason: Optional[str] = None,
    ) -> Self:
        bot = gameday.bot
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.gameday_members(gameday_id, team_id, member_id, guild_id, is_temporary_sub, reason) '
                'VALUES($1, $2, $3, $4, $5, $6) '
                'RETURNING *',
                gameday.id,
                gameday.team_id,
                user.id,
                gameday.guild_id,
                is_temporary_sub,
                reason,
            )
            assert data

        self = cls(bot, **dict(data))
        gameday.add_member(self)

        return self

    @property
    def is_attending(self) -> bool:
        return bool(self.reason)

    @property
    def gameday(self) -> Optional[Gameday]:
        team = self.team
        bucket = team.get_gameday_bucket()
        if bucket is None:
            return

        return bucket.get_gameday(self.gameday_id)

    async def delete(self) -> None:
        bot = self.bot
        async with bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM teams.gameday_members WHERE id = $1',
                self.id,
            )

        gameday = self.gameday
        if gameday is not None:
            gameday.remove_member(self.member_id)

    async def edit(self, *, is_temporary_sub: bool = MISSING, reason: str = MISSING) -> None:
        query = QueryBuilder('teams.gameday_members')
        query.add_condition('id', self.id)

        if is_temporary_sub is not MISSING:
            query.add_arg('is_temporary_sub', is_temporary_sub)
            self.is_temporary_sub = is_temporary_sub

        if reason is not MISSING:
            query.add_arg('reason', reason)
            self.reason = reason

        await query(self.bot)


@dataclasses.dataclass()
class GamedayImage(Teamable):
    bot: FuryBot
    id: int
    gameday_id: int
    team_id: int
    guild_id: int
    image_url: str
    uploader_id: int
    uploaded_at: datetime.datetime

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    @property
    def bucket(self) -> GamedayBucket:
        bucket = self.bot.get_gameday_bucket(self.guild_id, self.team_id)
        assert bucket is not None
        return bucket


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
        advance_gameday_notification_message_id: Optional[int] = None,
        scoreboard_message_id: Optional[int] = None,
        images: List[GamedayImage] = [],
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

        # The message ID of the advance gameday notification message, also known as the panel
        # that determines who is and isn't coming to the gameday.
        self.attendance_voting_message_id: Optional[int] = advance_gameday_notification_message_id
        self.attendance_voting_start: datetime.datetime = _get_attendance_voting_start_time(self.started_at)
        self.attendance_voting_end: datetime.datetime = _get_attendance_voting_end_time(self.started_at)

        self.scoreboard_message_id: Optional[int] = scoreboard_message_id
        self.scoreboard: ScoreboardPanel = ScoreboardPanel(self)

        if self.scoreboard_message_id and self.ongoing:
            bot.add_view(self.scoreboard, message_id=self.scoreboard_message_id)

        self.images: List[GamedayImage] = images

    def _get_bot(self) -> FuryBot:
        return self.bot

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        gameday_bucket_id: int,
        guild_id: int,
        team_id: int,
        starts_at: datetime.datetime,
    ) -> Self:
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.gamedays (bucket_id, guild_id, team_id, started_at) VALUES ($1, $2, $3, $4) RETURNING *',
                gameday_bucket_id,
                guild_id,
                team_id,
                starts_at,
            )
            assert data

        self = cls(bot=bot, **dict(data))
        self.bucket.add_gameday(self)

        # Let's spawn some tasks to start this gameday here
        timer_manager = self.bot.timer_manager
        if timer_manager is not None:
            # Create a timer for when the gameday starts.
            default_timer_args = (guild_id, team_id, gameday_bucket_id, self.id)

            await timer_manager.create_timer(starts_at, 'gameday_start', *default_timer_args)

            # Create a timer for the start and end of the voting
            await timer_manager.create_timer(self.attendance_voting_start, 'attendance_voting_start', *default_timer_args)
            await timer_manager.create_timer(self.attendance_voting_end, 'attendance_voting_end', *default_timer_args)

        return self

    @classmethod
    async def fetch_members(
        cls: Type[Self], bot: FuryBot, gameday_id: int, *, connection: ConnectionType
    ) -> Dict[int, GamedayMember]:
        data = await connection.fetch(
            'SELECT * FROM teams.gameday_members WHERE gameday_id = $1',
            gameday_id,
        )

        return {row['member_id']: GamedayMember(bot=bot, **dict(row)) for row in data}

    @classmethod
    async def fetch_images(
        cls: Type[Self], bot: FuryBot, gameday_id: int, *, connection: ConnectionType
    ) -> List[GamedayImage]:
        data = await connection.fetch('SELECT * FROM teams.gameday_images WHERE gameday_id = $1', gameday_id)

        return [GamedayImage(bot=bot, **dict(row)) for row in data]

    @property
    def subs_needed(self) -> int:
        return self.bucket.members_on_team - len(self.get_members())

    @property
    def bucket(self) -> GamedayBucket:
        bucket = self.bot.get_gameday_bucket(self.guild_id, self.team_id)
        assert bucket is not None
        return bucket

    @property
    def is_full(self) -> bool:
        return self.subs_needed <= 0

    @property
    def ongoing(self) -> bool:
        return bool(self.ended_at)

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

    def get_members_not_attending(self) -> Dict[int, GamedayMember]:
        return {k: v for k, v in self._members.items() if not v.is_attending}

    def add_image(self, image: GamedayImage) -> None:
        self.images.append(image)

    def remove_image(self, image: GamedayImage) -> None:
        self.images.remove(image)

    # A function to determine if the team has won or lost the gameday
    # based on the score of the gameday and the bucket's "best_of" value.
    def has_won(self) -> bool:
        return self.wins >= self.bucket.best_of

    def has_lost(self) -> bool:
        return self.losses >= self.bucket.best_of

    def inject_metadata_into_embed(self, embed: discord.Embed) -> None:
        attending_members = self.get_members_attending()

        members: List[str] = []
        subs: List[str] = []
        for attending_member in attending_members.values():
            if attending_member.is_temporary_sub:
                subs.append(f'- {attending_member.mention} (One-Time Sub)')
                continue

            team_member = self.team.get_member(attending_member.member_id)
            assert team_member  # A member can only be in this list of they're on the team

            if team_member.is_sub:
                subs.append(f'- {attending_member.mention}')
                continue

            members.append(f'- {attending_member.mention}')

        embed.add_field(
            name='Attending Members',
            value='\n'.join(members) or 'No members have selected themselves as attending.',
            inline=False,
        )

        if subs:
            embed.add_field(name='Attending Subs', value='\n'.join(subs), inline=False)

        not_attending_formatted = '\n'.join(f'{m.mention}: {m.reason}' for m in self.get_members_not_attending().values())
        embed.add_field(
            name='Not Attending Members',
            value=not_attending_formatted or 'No members have marked themselves as not attending.',
            inline=False,
        )

        if self.images:
            embed.set_image(url='attachment://gameday.png')

    async def edit(
        self,
        *,
        attendance_voting_message_id: int = MISSING,
        wins: int = MISSING,
        losses: int = MISSING,
        ended_at: datetime.datetime = MISSING,
        scoreboard_message_id: int = MISSING,
    ) -> None:
        query_builder = QueryBuilder('teams.gamedays')
        query_builder.add_condition('id', self.id)

        if attendance_voting_message_id is not MISSING:
            query_builder.add_arg('attendance_voting_message_id', attendance_voting_message_id)
            self.attendance_voting_message_id = attendance_voting_message_id

        if wins is not MISSING:
            query_builder.add_arg('wins', wins)
            self.wins = wins

        if losses is not MISSING:
            query_builder.add_arg('losses', losses)
            self.losses = losses

        if ended_at is not MISSING:
            query_builder.add_arg('ended_at', ended_at)
            self.ended_at = ended_at

        if scoreboard_message_id is not MISSING:
            query_builder.add_arg('scoreboard_message_id', scoreboard_message_id)
            self.scoreboard_message_id = scoreboard_message_id

        await query_builder(self.bot)

    async def end(self, *, when: Optional[datetime.datetime] = None) -> None:
        when = when or discord.utils.utcnow()

        # And let's set the ended_at timestamp.
        await self.edit(ended_at=when)

        if self.scoreboard_message_id:
            channel = self.team.text_channel
            message = channel.get_partial_message(self.scoreboard_message_id)

            await message.edit(view=None)

            captain_mentions = ', '.join([r.mention for r in self.team.captain_roles])

            # TODO: Maybe provide a better embed?
            await message.reply(
                content=f'{captain_mentions} The gameday has ended.',
                allowed_mentions=discord.AllowedMentions(roles=True),
            )

    async def merge_gameday_images(self) -> Optional[discord.File]:
        if not self.images:
            return None

        image = await image_from_urls(self.bot, [image.image_url for image in self.images], images_per_row=2)
        file = image_to_file(image, filename='gameday.png', description='Gameday Images')
        return file


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
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        guild_id: int,
        team_id: int,
        members_on_team: int,
        weekday: Weekday,
        game_time: datetime.time,
        best_of: int,
        automatic_sub_finding: bool = True,
    ) -> Self:
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.gameday_buckets (team_id, guild_id, weekday, game_time, members_on_team, best_of, automatic_sub_finding) '
                'VALUES($1, $2, $3, $4, $5, $6, $7) '
                'RETURNING *',
                team_id,
                guild_id,
                weekday.value,
                game_time,
                members_on_team,
                best_of,
                automatic_sub_finding,
            )
            assert data

        self = cls(bot=bot, **dict(data))
        bot.add_gameday_bucket(self)

        # Let's create the first gameday as well for this bucket which will start
        # the cycle of timers.
        gameday_time = _get_next_gameday_time(discord.utils.utcnow(), weekday=weekday, game_time=game_time)
        await Gameday.create(bot, gameday_bucket_id=self.id, guild_id=guild_id, team_id=team_id, starts_at=gameday_time)

        return self

    @classmethod
    async def fetch_gamedays(
        cls: Type[Self], bot: FuryBot, gameday_bucket_id: int, *, connection: ConnectionType
    ) -> List[Gameday]:
        gamedays: List[Gameday] = []
        data = await connection.fetch('SELECT * FROM teams.gamedays WHERE bucket_id = $1', gameday_bucket_id)

        for row in data:
            members = await Gameday.fetch_members(bot=bot, gameday_id=row['id'], connection=connection)
            images = await Gameday.fetch_images(bot=bot, gameday_id=row['id'], connection=connection)
            gameday = Gameday(bot=bot, members=members, images=images, **dict(row))
            gamedays.append(gameday)

        return gamedays

    @property
    def wins_needed(self) -> int:
        return math.ceil(self.best_of / 2)

    @property
    def ongoing_gameday(self) -> Optional[Gameday]:
        return discord.utils.find(lambda gameday: gameday.ongoing and gameday.started_at < discord.utils.utcnow(), self._gamedays.values())

    def get_gamedays(self) -> Mapping[int, Gameday]:
        return self._gamedays

    def get_gameday(self, gameday_id: int) -> Optional[Gameday]:
        return self._gamedays.get(gameday_id)

    def add_gameday(self, gameday: Gameday) -> None:
        self._gamedays[gameday.id] = gameday

    def remove_gameday(self, gameday_id: int) -> None:
        self._gamedays.pop(gameday_id, None)

    async def edit(
        self,
        *,
        weekday: Weekday = MISSING,
        game_time: datetime.time = MISSING,
        members_on_team: int = MISSING,
        best_of: int = MISSING,
        automatic_sub_finding: bool = MISSING,
    ) -> None:
        query_builder = QueryBuilder('teams.gameday_buckets')
        query_builder.add_arg('id', self.id)

        if weekday is not MISSING:
            query_builder.add_arg('weekday', weekday.value)
            self.weekday = weekday

        if game_time is not MISSING:
            query_builder.add_arg('game_time', game_time)
            self.game_time = game_time

        if members_on_team is not MISSING:
            query_builder.add_arg('members_on_team', members_on_team)
            self.members_on_team = members_on_team

        if best_of is not MISSING:
            query_builder.add_arg('best_of', best_of)
            self.best_of = best_of

        if automatic_sub_finding is not MISSING:
            query_builder.add_arg('automatic_sub_finding', automatic_sub_finding)
            self.automatic_sub_finding = automatic_sub_finding

        await query_builder(self.bot)
