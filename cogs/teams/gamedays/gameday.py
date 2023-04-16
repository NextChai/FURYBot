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
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Type, Union

import discord
import pytz
from typing_extensions import Self

from utils import QueryBuilder, TimerNotFound, image_from_urls, image_to_file

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot
    from cogs.teams.team import Team
    from utils.timers import Timer

MISSING = discord.utils.MISSING

VotingTimes = NamedTuple(
    'VotingTimes', [('start', datetime.datetime), ('end', datetime.datetime), ('can_use_automatic_sub_finding', bool)]
)

EST = pytz.timezone('US/Eastern')


def _determine_default_voting_times(gameday_starts_at: datetime.datetime) -> VotingTimes:
    midnight = gameday_starts_at.replace(hour=0, minute=0, second=0, microsecond=0)

    voting_start_time = midnight - datetime.timedelta(hours=9)
    voting_end_time = voting_start_time + datetime.timedelta(hours=5)

    return VotingTimes(start=voting_start_time, end=voting_end_time, can_use_automatic_sub_finding=True)


def determine_comfy_voting_times(gameday_starts_at: datetime.datetime) -> VotingTimes:
    now = discord.utils.utcnow()

    time_until_gameday = gameday_starts_at - now

    if gameday_starts_at < now:
        # This time is already in the past, we need to raise an error
        raise ValueError('Gameday starts at a time in the past')

    # If there's less than 24 hours until the gameday, start the voting now and then end it N minutes before the gameday starts
    if time_until_gameday < datetime.timedelta(hours=24):
        if time_until_gameday < datetime.timedelta(hours=6):

            # If gameday starts at - voting_ends_at returns something that is before now, we need to edit the voting_ends_offset
            # so that it's not in the past
            voting_ends_offset = datetime.timedelta(minutes=5)
            if gameday_starts_at - voting_ends_offset < now:
                # Determine a new voting_ends_offset that ensures that voting ends time is in the future
                # and ends before the gameday starts
                voting_ends_offset = gameday_starts_at - now

            # There's less than 6 hours, start it now and end it 5 minutes before the gameday starts
            return VotingTimes(start=now, end=gameday_starts_at - voting_ends_offset, can_use_automatic_sub_finding=False)

        # There's more than 6 hours, start it now and end it 1 hour before the gameday starts
        return VotingTimes(
            start=now, end=gameday_starts_at - datetime.timedelta(hours=1), can_use_automatic_sub_finding=False
        )

    # Let's check if now is before the default voting start time. If it is, we use the defaults.
    default_voting_times = _determine_default_voting_times(gameday_starts_at)

    if default_voting_times.start > now:
        return default_voting_times

    # If we're here, it means that the default voting times have already passed. So we can start it now and wend it 5 hours from now
    return VotingTimes(start=now, end=now + datetime.timedelta(hours=5), can_use_automatic_sub_finding=True)


def get_next_gameday_time(*, weekday: Weekday, game_time: datetime.time) -> datetime.datetime:
    # The game_time variable was given in EST time, so we need to make sure to convert it to UTC time which is what the
    # bot works off of.

    now_est = datetime.datetime.now(EST).replace(
        hour=game_time.hour, minute=game_time.minute, second=game_time.second, microsecond=game_time.microsecond
    )

    # Now we need to get the next occurance of the given weekday.
    est_weekday = now_est.weekday()
    days_until_gameday = (weekday.value - est_weekday - 1) % 7

    # We can add days until gameday to now_est to get the next gameday time in EST time.
    now_est = now_est + datetime.timedelta(days=days_until_gameday)

    # Convert to UTC time now
    utc_datetime = now_est.astimezone(pytz.utc)

    return utc_datetime


class Weekday(enum.IntEnum):
    """Represents a weekday."""

    monday = 1
    tuesday = 2
    wednesday = 3
    thursday = 4
    friday = 5
    saturday = 6
    sunday = 7


@dataclasses.dataclass()
class GamedayMember:
    bot: FuryBot

    id: int
    member_id: int
    team_id: int
    guild_id: int
    bucket_id: int
    gameday_id: int
    reason: Optional[str]
    is_temporary_sub: bool

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        member_id: int,
        team_id: int,
        guild_id: int,
        bucket_id: int,
        gameday_id: int,
        reason: Optional[str] = None,
    ) -> Self:
        bucket = bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            raise ValueError('Cannot add member to a non-existing bucket.')

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            raise ValueError('Cannot add member to a non-existing gameday.')

        query = """
            INSERT INTO teams.gameday_members (
                member_id,
                team_id,
                guild_id,
                bucket_id,
                gameday_id,
                reason
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
            """

        data = await connection.fetchrow(query, member_id, team_id, guild_id, bucket_id, gameday_id, reason)
        assert data

        self = cls(bot=bot, **dict(data))
        gameday.add_member(self)

        return self

    @property
    def is_attending(self) -> bool:
        return not bool(self.reason)

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def mention(self) -> str:
        return f'<@{self.member_id}>'

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_members
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        if self.is_temporary_sub:
            team = self.team
            if team and (team_member := team.get_member(self.member_id)):
                await team.remove_team_member(team_member)

        gameday = self.gameday
        if gameday is None:
            return

        gameday.remove_member(self.id)

    async def edit(
        self, connection: ConnectionType, *, reason: Optional[str] = MISSING, is_temporary_sub: bool = MISSING
    ) -> None:
        builder = QueryBuilder('teams.gameday_members')
        builder.add_condition('id', self.id)

        if reason is not MISSING:
            builder.add_arg('reason', reason)
            self.reason = reason

        if is_temporary_sub is not MISSING:
            builder.add_arg('is_temporary_sub', is_temporary_sub)
            self.is_temporary_sub = is_temporary_sub

        await builder(connection)


@dataclasses.dataclass()
class GamedayImage:
    bot: FuryBot

    id: int
    guild_id: int
    team_id: int
    gameday_id: int
    bucket_id: int
    url: str
    uploader_id: int
    uploaded_at: datetime.datetime

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        guild_id: int,
        team_id: int,
        gameday_id: int,
        bucket_id: int,
        url: str,
        uploader_id: int,
        uploaded_at: datetime.datetime = discord.utils.utcnow(),
    ) -> Self:
        bucket = bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            raise ValueError('Cannot add image to a non-existing bucket.')

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            raise ValueError('Cannot add image to a non-existing gameday.')

        query = """
            INSERT INTO teams.gameday_images (
                guild_id,
                team_id,
                gameday_id,
                bucket_id,
                url,
                uploader_id,
                uploaded_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """

        data = await connection.fetchrow(query, guild_id, team_id, gameday_id, bucket_id, url, uploader_id, uploaded_at)
        assert data

        self = cls(bot=bot, **dict(data))
        gameday.add_image(self)

        return self

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_images
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        gameday = self.gameday
        if gameday is None:
            return

        gameday.remove_image(self.id)

    async def edit(
        self,
        connection: ConnectionType,
        *,
        url: str = MISSING,
        uploader_id: int = MISSING,
        uploaded_at: datetime.datetime = MISSING,
    ) -> None:
        builder = QueryBuilder('teams.gameday_images')
        builder.add_condition('id', self.id)

        if url is not MISSING:
            builder.add_arg('url', url)
            self.url = url

        if uploader_id is not MISSING:
            builder.add_arg('uploader_id', uploader_id)
            self.uploader_id = uploader_id

        if uploaded_at is not MISSING:
            builder.add_arg('uploaded_at', uploaded_at)
            self.uploaded_at = uploaded_at

        await builder(connection)


@dataclasses.dataclass()
class GamedayScoreReport:
    bot: FuryBot

    id: int
    guild_id: int
    team_id: int
    bucket_id: int
    gameday_id: int
    text: str
    reported_by_id: int
    reported_at: datetime.datetime

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        gameday_id: int,
        text: str,
        reported_by_id: int,
        reported_at: datetime.datetime = discord.utils.utcnow(),
    ) -> Self:
        bucket = bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            raise ValueError('Cannot add score report to a non-existing bucket.')

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            raise ValueError('Cannot add score report to a non-existing gameday.')

        query = """
            INSERT INTO teams.gameday_score_reports (
                guild_id,
                team_id,
                bucket_id,
                gameday_id,
                text,
                reported_by_id,
                reported_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETRNING *
            """

        data = await connection.fetchrow(query, guild_id, team_id, bucket_id, gameday_id, text, reported_by_id, reported_at)
        assert data

        self = cls(bot=bot, **dict(data))
        gameday.add_score_report(self)

        return self

    @property
    def reported_by(self) -> Optional[discord.User]:
        return self.bot.get_user(self.reported_by_id)

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_score_reports
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        gameday = self.gameday
        if gameday is None:
            return

        gameday.remove_score_report(self.id)

    async def edit(
        self,
        connection: ConnectionType,
        *,
        text: str = MISSING,
        reported_by_id: int = MISSING,
        reported_at: datetime.datetime = MISSING,
    ) -> None:
        builder = QueryBuilder('teams.gameday_score_reports')
        builder.add_condition('id', self.id)

        if text is not MISSING:
            builder.add_arg('text', text)
            self.text = text

        if reported_by_id is not MISSING:
            builder.add_arg('reported_by_id', reported_by_id)
            self.reported_by_id = reported_by_id

        if reported_at is not MISSING:
            builder.add_arg('reported_at', reported_at)
            self.reported_at = reported_at

        await builder(connection)

    async def fetch_reported_by(self) -> discord.User:
        return await self.bot.fetch_user(self.reported_by_id)


@dataclasses.dataclass()
class GamedayAttendanceVoting:
    bot: FuryBot

    guild_id: int
    team_id: int
    bucket_id: int
    gameday_id: int
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    starts_at_timer_id: Optional[int] = None
    ends_at_timer_id: Optional[int] = None
    message_id: Optional[int] = None

    @classmethod
    def from_data(
        cls: Type[Self],
        bot: FuryBot,
        *,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        gameday_id: int,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        starts_at_timer_id: Optional[int],
        ends_at_timer_id: Optional[int],
        message_id: Optional[int] = None,
    ) -> Self:
        return cls(
            bot=bot,
            guild_id=guild_id,
            team_id=team_id,
            bucket_id=bucket_id,
            gameday_id=gameday_id,
            starts_at=starts_at,
            ends_at=ends_at,
            starts_at_timer_id=starts_at_timer_id,
            ends_at_timer_id=ends_at_timer_id,
            message_id=message_id,
        )

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def message(self) -> Optional[discord.Message]:
        if self.message_id is None:
            return

        return discord.utils.find(lambda m: m.id == self.message_id, self.bot.cached_messages)

    @property
    def has_votes_needed(self) -> bool:
        bucket = self.bucket
        if bucket is None:
            raise ValueError('Bucket not found')

        gameday = self.gameday
        if gameday is None:
            raise ValueError('Gameday not found')

        return len(gameday.attending_members) == bucket.per_team

    async def fetch_message(self) -> Optional[discord.Message]:
        if self.message_id is None:
            return

        team = self.team
        if team is None:
            return

        return await team.text_channel.fetch_message(self.message_id)

    async def fetch_starts_at_timer(self, *, connection: Optional[ConnectionType] = None) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.starts_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.starts_at_timer_id, connection=connection)

    async def fetch_ends_at_timer(self, *, connection: Optional[ConnectionType] = None) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.ends_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.ends_at_timer_id, connection=connection)


@dataclasses.dataclass()
class Gameday:
    def __init__(
        self,
        bot: FuryBot,
        *,
        members: Dict[int, GamedayMember] = {},
        images: Dict[int, GamedayImage] = {},
        score_reports: Dict[int, GamedayScoreReport] = {},
        id: int,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        starts_at: datetime.datetime,
        ended_at: Optional[datetime.datetime] = None,
        automatic_sub_finding: bool,
        voting_starts_at: datetime.datetime,
        voting_ends_at: datetime.datetime,
        gameday_time_id: int,
        voting_starts_at_timer_id: Optional[int] = None,
        voting_ends_at_timer_id: Optional[int] = None,
        starts_at_timer_id: Optional[int] = None,
        voting_message_id: Optional[int] = None,
        score_message_id: Optional[int] = None,
    ) -> None:
        self.bot: FuryBot = bot

        self.members: Dict[int, GamedayMember] = members
        self.images: Dict[int, GamedayImage] = images
        self.score_reports: Dict[int, GamedayScoreReport] = score_reports

        self.id: int = id
        self.guild_id: int = guild_id
        self.team_id: int = team_id
        self.bucket_id: int = bucket_id
        self.starts_at: datetime.datetime = starts_at
        self.ended_at: Optional[datetime.datetime] = ended_at
        self.automatic_sub_finding: bool = automatic_sub_finding
        self.starts_at_timer_id: Optional[int] = starts_at_timer_id
        self.gameday_time_id: int = gameday_time_id

        self.score_message_id: Optional[int] = score_message_id

        self.voting = GamedayAttendanceVoting.from_data(
            self.bot,
            guild_id=guild_id,
            team_id=team_id,
            bucket_id=bucket_id,
            gameday_id=self.id,
            starts_at=voting_starts_at,
            ends_at=voting_ends_at,
            starts_at_timer_id=voting_starts_at_timer_id,
            ends_at_timer_id=voting_ends_at_timer_id,
            message_id=voting_message_id,
        )

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        gameday_time_id: int,
        starts_at: datetime.datetime,
    ) -> Self:

        bucket = bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            raise ValueError(f"Bucket {bucket_id} does not exist")

        voting = determine_comfy_voting_times(starts_at)

        query = """
            INSERT INTO teams.gamedays (
                guild_id,
                team_id, 
                bucket_id, 
                starts_at,
                automatic_sub_finding, 
                voting_starts_at,
                voting_ends_at,
                gameday_time_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """

        data = await connection.fetchrow(
            query,
            guild_id,
            team_id,
            bucket_id,
            starts_at,
            voting.can_use_automatic_sub_finding,
            voting.start,
            voting.end,
            gameday_time_id,
        )
        assert data

        self = cls(bot=bot, members={}, images={}, score_reports={}, **dict(data))
        bucket.add_gameday(self)

        # We need to spawn the timers here to dispatch the events
        timer_manager = bot.timer_manager
        if timer_manager:  # This will be Not none in non-development environments
            default_timer_args = (guild_id, team_id, self.id)
            gameday_start_timer = await timer_manager.create_timer(starts_at, 'gameday_start', *default_timer_args)

            voting_start_timer = await timer_manager.create_timer(voting.start, 'gameday_voting_start', *default_timer_args)
            voting_end_timer = await timer_manager.create_timer(voting.end, 'gameday_voting_end', *default_timer_args)

            await self.edit(
                connection,
                voting_starts_at_timer_id=voting_start_timer.id,
                voting_ends_at_timer_id=voting_end_timer.id,
                starts_at_timer_id=gameday_start_timer.id,
            )

        return self

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def time(self) -> Optional[GamedayTime]:
        bucket = self.bucket
        if bucket is None:
            return

        return bucket.get_gameday_time(self.gameday_time_id)

    @property
    def attending_members(self) -> List[GamedayMember]:
        return [member for member in self.members.values() if member.is_attending]

    @property
    def not_attending_members(self) -> List[GamedayMember]:
        return [member for member in self.members.values() if not member.is_attending]

    @property
    def has_ended(self):
        return bool(self.ended_at)

    def add_score_report(self, report: GamedayScoreReport) -> None:
        self.score_reports[report.id] = report

    def remove_score_report(self, report_id: int, /) -> Optional[GamedayScoreReport]:
        return self.score_reports.pop(report_id, None)

    def get_score_report(self, report_id: int, /) -> Optional[GamedayScoreReport]:
        return self.score_reports.get(report_id)

    def add_member(self, member: GamedayMember) -> None:
        self.members[member.member_id] = member

    def remove_member(self, member_id: int, /) -> Optional[GamedayMember]:
        return self.members.pop(member_id, None)

    def get_member(self, member_id: int) -> Optional[GamedayMember]:
        return self.members.get(member_id)

    def get_members(self) -> List[GamedayMember]:
        return list(self.members.values())

    def add_image(self, image: GamedayImage, /) -> None:
        self.images[image.id] = image

    def remove_image(self, image_id: int, /) -> Optional[GamedayImage]:
        return self.images.pop(image_id, None)

    def get_image(self, image_id: int, /) -> Optional[GamedayImage]:
        return self.images.get(image_id)

    async def merge_images(self) -> Optional[discord.File]:
        if not self.images:
            return

        image = await image_from_urls(
            self.bot, urls=[i.url for i in self.images.values()], images_per_row=3, frame_width=1920, normalize_images=True
        )
        return image_to_file(image, filename='gameday_images.png', description='The merged image for all gameday images.')

    async def create_member(
        self, member_id: int, *, reason: Optional[str] = None, connection: ConnectionType
    ) -> GamedayMember:
        return await GamedayMember.create(
            self.bot,
            connection=connection,
            member_id=member_id,
            team_id=self.team_id,
            guild_id=self.guild_id,
            bucket_id=self.bucket_id,
            gameday_id=self.id,
            reason=reason,
        )

    async def fetch_members(self, *, connection: ConnectionType) -> List[GamedayMember]:
        query = """
            SELECT *
            FROM teams.gameday_members
            WHERE gameday_id = $1
            """

        data = await connection.fetch(query, self.id)
        return [GamedayMember(self.bot, **dict(row)) for row in data]

    async def fetch_images(self, *, connection: ConnectionType) -> List[GamedayImage]:
        query = """
            SELECT *
            FROM teams.gameday_images
            WHERE gameday_id = $1
            """

        data = await connection.fetch(query, self.id)
        return [GamedayImage(self.bot, **dict(row)) for row in data]

    async def fetch_score_reports(self, *, connection: ConnectionType) -> List[GamedayScoreReport]:
        query = """
            SELECT *
            FROM teams.gameday_score_reports
            WHERE gameday_id = $1
            """

        data = await connection.fetch(query, self.id)
        return [GamedayScoreReport(self.bot, **dict(row)) for row in data]

    async def setup(self, *, connection: ConnectionType) -> None:
        members = await self.fetch_members(connection=connection)
        for member in members:
            self.add_member(member)

        images = await self.fetch_images(connection=connection)
        for image in images:
            self.add_image(image)

        scores = await self.fetch_score_reports(connection=connection)
        for score in scores:
            self.add_score_report(score)

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gamedays
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        bucket = self.bucket
        if bucket is None:
            return

        # We need to fetch the timers here to delete them
        timer_coros = [self.fetch_starts_at_timer, self.voting.fetch_starts_at_timer, self.voting.fetch_ends_at_timer]

        for coro in timer_coros:
            try:
                timer = await coro(connection=connection)
            except TimerNotFound:
                pass
            else:
                if timer is not None:
                    await timer.delete(connection=connection)

        if self.ended_at is None and self.starts_at < discord.utils.utcnow():
            # This gameday has not ended yet, so we need to remove any messages that were created
            # and any members from the team that were added as temporary subs
            voting_message = self.voting.message or await self.voting.fetch_message()
            if voting_message is not None:
                await voting_message.delete()

            # Remove all temporary subs but keep them in the voice channels
            # until the gameday ends
            team = self.team
            if team is not None:
                for member in self.members.values():
                    if member.is_temporary_sub and (team_member := team.get_member(member.member_id)):
                        await team.remove_team_member(team_member, force_voice_disconnect=False)

        bucket.remove_gameday(self.id)

    async def fetch_starts_at_timer(self, *, connection: Optional[ConnectionType] = None) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.starts_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.starts_at_timer_id, connection=connection)

    async def edit(
        self,
        connection: ConnectionType,
        *,
        starts_at: datetime.datetime = MISSING,
        automatic_sub_finding: bool = MISSING,
        voting_starts_at: datetime.datetime = MISSING,
        voting_ends_at: datetime.datetime = MISSING,
        voting_starts_at_timer_id: int = MISSING,
        voting_ends_at_timer_id: int = MISSING,
        voting_message_id: int = MISSING,
        starts_at_timer_id: int = MISSING,
        ended_at: datetime.datetime = MISSING,
        score_message_id: int = MISSING,
    ) -> None:
        builder = QueryBuilder('teams.gamedays')
        builder.add_condition('id', self.id)

        if starts_at is not MISSING:
            builder.add_arg('starts_at', starts_at)
            self.starts_at = starts_at

        if automatic_sub_finding is not MISSING:
            builder.add_arg('automatic_sub_finding', automatic_sub_finding)
            self.automatic_sub_finding = automatic_sub_finding

        if voting_starts_at is not MISSING:
            builder.add_arg('voting_starts_at', voting_starts_at)
            self.voting.starts_at = voting_starts_at

        if voting_ends_at is not MISSING:
            builder.add_arg('voting_ends_at', voting_ends_at)
            self.voting.ends_at = voting_ends_at

        if voting_starts_at_timer_id is not MISSING:
            builder.add_arg('voting_starts_at_timer_id', voting_starts_at_timer_id)
            self.voting.starts_at_timer_id = voting_starts_at_timer_id

        if voting_ends_at_timer_id is not MISSING:
            builder.add_arg('voting_ends_at_timer_id', voting_ends_at_timer_id)
            self.voting.ends_at_timer_id = voting_ends_at_timer_id

        if voting_message_id is not MISSING:
            builder.add_arg('voting_message_id', voting_message_id)
            self.voting.message_id = voting_message_id

        if starts_at_timer_id is not MISSING:
            builder.add_arg('starts_at_timer_id', starts_at_timer_id)
            self.starts_at_timer_id = starts_at_timer_id

        if ended_at is not MISSING:
            builder.add_arg('ended_at', ended_at)
            self.ended_at = ended_at

        if score_message_id is not MISSING:
            builder.add_arg('score_message_id', score_message_id)
            self.score_message_id = score_message_id

        if self.bot.timer_manager:
            updating_timers = [
                (starts_at, self.fetch_starts_at_timer),
                (voting_starts_at, self.voting.fetch_starts_at_timer),
                (voting_ends_at, self.voting.fetch_ends_at_timer),
            ]

            for new_datetime, coro in updating_timers:
                if new_datetime is MISSING:
                    continue

                try:
                    timer = await coro(connection=connection)
                except TimerNotFound:
                    continue
                else:
                    if timer is not None:
                        await timer.edit(expires=new_datetime)

        await builder(connection)


@dataclasses.dataclass()
class GamedayTime:
    def __init__(
        self,
        bot: FuryBot,
        *,
        id: int,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        weekday: Union[int, Weekday],
        starts_at: datetime.time,
    ) -> None:
        self.bot: FuryBot = bot

        self.id = id
        self.guild_id = guild_id
        self.team_id = team_id
        self.bucket_id = bucket_id
        self.weekday: Weekday = weekday if isinstance(weekday, Weekday) else Weekday(weekday)
        self.starts_at = starts_at

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        weekday: Weekday,
        starts_at: datetime.time,
    ) -> Self:
        bucket = bot.get_gameday_bucket(guild_id, team_id)
        if bucket is None:
            raise ValueError(f'Bucket {bucket_id} does not exist')

        query = """
            INSERT INTO teams.gameday_times (guild_id, team_id, bucket_id, weekday, starts_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """

        data = await connection.fetchrow(query, guild_id, team_id, bucket_id, weekday.value, starts_at)
        assert data

        self = cls(bot, **dict(data))
        bucket.add_gameday_time(self)

        # Let's spawn a new instance of Gameday for the next gameday with this time
        next_gameday_starts_at = get_next_gameday_time(weekday=self.weekday, game_time=self.starts_at)
        await Gameday.create(
            bot,
            connection=connection,
            guild_id=guild_id,
            team_id=team_id,
            bucket_id=bucket_id,
            starts_at=next_gameday_starts_at,
            gameday_time_id=self.id,
        )

        return self

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def gamedays(self) -> List[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return []

        return [gameday for gameday in bucket.gamedays.values() if gameday.gameday_time_id == self.id]

    async def edit(
        self,
        *,
        connection: ConnectionType,
        weekday: Weekday = MISSING,
        starts_at: datetime.time = MISSING,
    ) -> None:
        builder = QueryBuilder('teams.gameday_times')
        builder.add_condition('id', self.id)

        if weekday is not MISSING:
            builder.add_arg('weekday', weekday.value)
            self.weekday = weekday

        if starts_at is not MISSING:
            builder.add_arg('starts_at', starts_at)
            self.starts_at = starts_at

        if weekday is not MISSING or starts_at is not MISSING:
            # We need to update all the gamedays that have this time.

            weekday = weekday if weekday is not MISSING else self.weekday
            starts_at = starts_at if starts_at is not MISSING else self.starts_at

            # We need to edit all the gamedays that have this time.
            bucket = self.bucket
            if bucket is None:
                raise ValueError(f'Bucket {self.bucket_id} does not exist')

            now = discord.utils.utcnow()
            for gameday in bucket.gamedays.values():
                if gameday.gameday_time_id != self.id:
                    continue

                # continue if the gameday started in the past
                if gameday.starts_at < now:
                    continue

                if gameday.ended_at is not None:
                    # This gameday has already ended, there is no need to edit it.
                    continue

                new_starts_at = get_next_gameday_time(weekday=weekday, game_time=starts_at)
                voting = determine_comfy_voting_times(new_starts_at)

                await gameday.edit(
                    connection,
                    starts_at=new_starts_at,
                    voting_starts_at=voting.start,
                    voting_ends_at=voting.end,
                    automatic_sub_finding=voting.can_use_automatic_sub_finding,
                )

                # Some timers may need to be updated as well, so let's do that.
                timers = [
                    (gameday.voting.fetch_starts_at_timer, voting.start),
                    (gameday.voting.fetch_ends_at_timer, voting.end),
                    (gameday.fetch_starts_at_timer, new_starts_at),
                ]
                for timer_coro, new_time in timers:
                    try:
                        timer = await timer_coro(connection=connection)
                    except TimerNotFound:
                        continue
                    else:
                        if timer is not None:
                            await timer.edit(expires=new_time)

                # Let's update the message as well
                view = self.bot.attendance_voting_view
                if view is not None:
                    try:
                        voting_message = await gameday.voting.fetch_message()
                    except discord.NotFound:
                        continue
                    else:
                        if voting_message is None:
                            continue

                        embed = view.create_embed(gameday)
                        await voting_message.edit(embed=embed)

        await builder(connection)

    async def delete(self, *, connection: ConnectionType) -> List[Gameday]:
        query = """
            DELETE FROM teams.gameday_times WHERE id = $1
        """

        await connection.execute(query, self.id)

        bucket = self.bucket
        if bucket is None:
            return []

        # Delete all gamedays that have this time that do not have an ended_at
        gamedays = bucket.get_gamedays_with_time(self.id)
        removed_gamedays: List[Gameday] = []
        for gameday in gamedays:
            if gameday.ended_at is None:
                await gameday.delete(connection=connection)
                removed_gamedays.append(gameday)

        bucket.remove_gameday_time(self.id)

        return removed_gamedays


@dataclasses.dataclass()
class GamedayBucket:
    bot: FuryBot

    id: int
    guild_id: int
    team_id: int
    automatic_sub_finding_channel_id: Optional[int]
    automatic_sub_finding_if_possible: bool
    per_team: int

    gameday_times: Dict[int, GamedayTime] = dataclasses.field(default_factory=dict)
    gamedays: Dict[int, Gameday] = dataclasses.field(default_factory=dict)

    @classmethod
    async def create(
        cls: Type[Self],
        bot: FuryBot,
        *,
        connection: ConnectionType,
        guild_id: int,
        team_id: int,
        automatic_sub_finding_if_possible: bool = False,
        automatic_sub_finding_channel_id: Optional[int] = None,
        per_team: int,
    ) -> Self:
        query = """
            INSERT INTO teams.gameday_buckets (guild_id, team_id, automatic_sub_finding_if_possible, automatic_sub_finding_channel_id, per_team)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """

        data = await connection.fetchrow(
            query, guild_id, team_id, automatic_sub_finding_if_possible, automatic_sub_finding_channel_id, per_team
        )
        assert data

        self = cls(bot, gamedays={}, gameday_times={}, **dict(data))
        bot.add_gameday_bucket(self)

        return self

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def automatic_sub_finding_channel(self) -> Optional[discord.abc.GuildChannel]:
        if self.automatic_sub_finding_channel_id is None:
            return

        guild = self.guild
        if guild is None:
            return

        return guild.get_channel(self.automatic_sub_finding_channel_id)

    @property
    def ongoing_gamedays(self) -> List[Gameday]:
        now = discord.utils.utcnow()

        def _check(gameday: Gameday) -> bool:
            return gameday.ended_at is None and gameday.starts_at <= now

        return list(filter(_check, self.get_gamedays()))

    def add_gameday(self, gameday: Gameday) -> None:
        self.gamedays[gameday.id] = gameday

    def remove_gameday(self, gameday_id: int) -> Optional[Gameday]:
        self.gamedays.pop(gameday_id, None)

    def get_gameday(self, gameday_id: int) -> Optional[Gameday]:
        return self.gamedays.get(gameday_id)

    def get_gamedays(self) -> List[Gameday]:
        return list(self.gamedays.values())

    def get_gamedays_with_time(self, gameday_time_id: int, /) -> List[Gameday]:
        return [gameday for gameday in self.gamedays.values() if gameday.gameday_time_id == gameday_time_id]

    def add_gameday_time(self, gameday_time: GamedayTime) -> None:
        self.gameday_times[gameday_time.id] = gameday_time

    def remove_gameday_time(self, gameday_time_id: int) -> Optional[GamedayTime]:
        return self.gameday_times.pop(gameday_time_id, None)

    def get_gameday_time(self, gameday_time_id: int) -> Optional[GamedayTime]:
        return self.gameday_times.get(gameday_time_id)

    def get_gameday_times(self) -> List[GamedayTime]:
        return list(self.gameday_times.values())

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_buckets WHERE id = $1
        """

        await connection.execute(query, self.id)

        self.bot.remove_gameday_bucket(self.guild_id, self.team_id)

    async def fetch_gamedays(self, *, connection: ConnectionType) -> List[Gameday]:
        query = """
            SELECT *
            FROM teams.gamedays
            WHERE bucket_id = $1
        """

        data = await connection.fetch(query, self.id)
        return [Gameday(self.bot, **dict(row)) for row in data]

    async def fetch_gameday_times(self, *, connection: ConnectionType) -> List[GamedayTime]:
        query = """
            SELECT *
            FROM teams.gameday_times
            WHERE bucket_id = $1
        """

        data = await connection.fetch(query, self.id)
        return [GamedayTime(self.bot, **dict(row)) for row in data]

    async def setup(self, *, connection: ConnectionType) -> None:
        gamedays = await self.fetch_gamedays(connection=connection)
        for gameday in gamedays:
            await gameday.setup(connection=connection)
            self.add_gameday(gameday)

        times = await self.fetch_gameday_times(connection=connection)
        for time in times:
            self.add_gameday_time(time)

    async def edit(
        self,
        *,
        connection: ConnectionType,
        per_team: int = MISSING,
        automatic_sub_finding_if_possible: bool = MISSING,
        automatic_sub_finding_channel_id: Optional[int] = MISSING,
    ) -> None:
        builder = QueryBuilder('teams.gameday_buckets')
        builder.add_condition('id', self.id)

        if per_team is not MISSING:
            builder.add_arg('per_team', per_team)
            self.per_team = per_team

        if automatic_sub_finding_if_possible is not MISSING:
            builder.add_arg('automatic_sub_finding_if_possible', automatic_sub_finding_if_possible)
            self.automatic_sub_finding_if_possible = automatic_sub_finding_if_possible

        if automatic_sub_finding_channel_id is not MISSING:
            builder.add_arg('automatic_sub_finding_channel_id', automatic_sub_finding_channel_id)
            self.automatic_sub_finding_channel_id = automatic_sub_finding_channel_id

        await builder(connection=connection)
