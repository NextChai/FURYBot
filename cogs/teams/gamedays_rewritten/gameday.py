from __future__ import annotations

import dataclasses
import datetime
import enum
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Type, Union

import discord
from typing_extensions import Self

from utils import QueryBuilder

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot
    from cogs.teams.team import Team
    from utils.timers import Timer

MISSING = discord.utils.MISSING

VotingTimes = NamedTuple(
    'VotingTimes', [('start', datetime.datetime), ('end', datetime.datetime), ('can_use_automatic_sub_finding', bool)]
)


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
            # There's less than 6 hours, start it now and end it 5 minutes before the gameday starts
            return VotingTimes(
                start=now, end=gameday_starts_at - datetime.timedelta(minutes=5), can_use_automatic_sub_finding=False
            )

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
        bucket = bot.get_gameday_bucket(guild_id, team_id, bucket_id)
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

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_members
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        gameday = self.gameday
        if gameday is None:
            return

        gameday.remove_member(self.id)

    async def edit(self, connection: ConnectionType, *, reason: str = MISSING) -> None:
        builder = QueryBuilder('teams.gameday_members')
        builder.add_condition('id', self.id)

        if reason is not MISSING:
            builder.add_arg('reason', reason)
            self.reason = reason

        await builder(connection)

    @property
    def is_attending(self) -> bool:
        return not bool(self.reason)

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

    @property
    def mention(self) -> str:
        return f'<@{self.member_id}>'


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
        bucket = bot.get_gameday_bucket(guild_id, team_id, bucket_id)
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
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

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
        bucket = bot.get_gameday_bucket(guild_id, team_id, bucket_id)
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
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

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
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def gameday(self) -> Optional[Gameday]:
        bucket = self.bucket
        if bucket is None:
            return None

        return bucket.get_gameday(self.gameday_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

    @property
    def message(self) -> Optional[discord.Message]:
        if self.message_id is None:
            return

        return discord.utils.find(lambda m: m.id == self.message_id, self.bot.cached_messages)

    async def fetch_message(self) -> Optional[discord.Message]:
        if self.message_id is None:
            return

        team = self.team
        if team is None:
            return

        return await team.text_channel.fetch_message(self.message_id)

    async def fetch_starts_at_timer(self) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.starts_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.starts_at_timer_id)

    async def fetch_ends_at_timer(self) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.ends_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.ends_at_timer_id)


@dataclasses.dataclass()
class Gameday:
    def __init__(
        self,
        bot: FuryBot,
        *,
        members: Dict[int, GamedayMember],
        images: Dict[int, GamedayImage],
        score_reports: Dict[int, GamedayScoreReport],
        id: int,
        guild_id: int,
        team_id: int,
        bucket_id: int,
        starts_at: datetime.datetime,
        ended_at: Optional[datetime.datetime] = None,
        automatic_sub_finding: bool,
        voting_starts_at: datetime.datetime,
        voting_ends_at: datetime.datetime,
        voting_starts_at_timer_id: Optional[int] = None,
        voting_ends_at_timer_id: Optional[int] = None,
        starts_at_timer_id: Optional[int] = None,
        voting_message_id: Optional[int] = None,
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
        starts_at: datetime.datetime,
    ) -> Self:

        bucket = bot.get_gameday_bucket(guild_id, team_id, bucket_id)
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
                voting_ends_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """

        data = await connection.fetchrow(
            query, guild_id, team_id, bucket_id, starts_at, voting.can_use_automatic_sub_finding, voting.start, voting.end
        )
        assert data

        self = cls(bot=bot, members={}, images={}, score_reports={}, **dict(data))
        bucket.add_gameday(self)

        return self

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

    def add_score_report(self, report: GamedayScoreReport) -> None:
        self.score_reports[report.id] = report

    def remove_score_report(self, report_id: int, /) -> Optional[GamedayScoreReport]:
        return self.score_reports.pop(report_id, None)

    def get_score_report(self, report_id: int, /) -> Optional[GamedayScoreReport]:
        return self.score_reports.get(report_id)

    def add_member(self, member: GamedayMember) -> None:
        self.members[member.id] = member

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

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gamedays
            WHERE id = $1
            """

        await connection.execute(query, self.id)

        bucket = self.bucket
        if bucket is None:
            return

        bucket.remove_gameday(self.id)

    async def fetch_starts_at_timer(self) -> Optional[Timer]:
        timer_manager = self.bot.timer_manager
        if timer_manager is None:
            return None

        if self.starts_at_timer_id is None:
            return None

        return await timer_manager.fetch_timer(self.starts_at_timer_id)

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
        starts_at: datetime.datetime,
    ) -> Self:
        bucket = bot.get_gameday_bucket(guild_id, team_id, bucket_id)
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

        return self

    @property
    def bucket(self) -> Optional[GamedayBucket]:
        return self.bot.get_gameday_bucket(self.guild_id, self.team_id, self.bucket_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

    async def delete(self, *, connection: ConnectionType) -> None:
        query = """
            DELETE FROM teams.gameday_times WHERE id = $1
        """

        await connection.execute(query, self.id)

        bucket = self.bucket
        if bucket is None:
            return

        bucket.remove_gameday_time(self.id)


@dataclasses.dataclass()
class GamedayBucket:
    bot: FuryBot

    gamedays: Dict[int, Gameday]
    id: int
    guild_id: int
    team_id: int
    gameday_times: Dict[int, GamedayTime]
    automatic_sub_finding_channel_id: Optional[int]
    automatic_sub_finding_if_possible: bool

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
    ) -> Self:
        query = """
            INSERT INTO teams.gameday_buckets (guild_id, team_id, automatic_sub_finding_if_possible, automatic_sub_finding_channel_id)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """

        data = await connection.fetchrow(
            query, guild_id, team_id, automatic_sub_finding_if_possible, automatic_sub_finding_channel_id
        )
        assert data

        self = cls(bot, **dict(data))
        bot.add_gameday_bucket(self)

        return self

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.guild_id, self.team_id)

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

    def add_gameday(self, gameday: Gameday) -> None:
        self.gamedays[gameday.id] = gameday

    def remove_gameday(self, gameday_id: int) -> Optional[Gameday]:
        self.gamedays.pop(gameday_id, None)

    def get_gameday(self, gameday_id: int) -> Optional[Gameday]:
        return self.gamedays.get(gameday_id)

    def get_gamedays(self) -> List[Gameday]:
        return list(self.gamedays.values())

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

        self.bot.remove_gameday_bucket(self.guild_id, self.team_id, self.id)
