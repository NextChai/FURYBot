"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to 
non-commercial purposes. Distribution, sublicensing, and sharing of this file 
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not 
misrepresent the original material. This license does not grant any 
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import datetime
import enum
import logging
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import discord

from utils import TeamAble, TeamMemberAble, human_timedelta

from ..errors import MemberNotOnTeam
from .errors import MemberAlreadyInPractice, MemberNotAttendingPractice, MemberNotInPractice
from .persistent import PracticeView

if TYPE_CHECKING:
    from bot import FuryBot

    from ..team import Team, TeamMember

__all__: Tuple[str, ...] = ('Practice', 'PracticeMember', 'PracticeMemberHistory', 'PracticeStatus')

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)  # A temporary placeholder until everything is done.

BONUS_STRENGTH: float = 0.2


class PracticeMemberHistory(TeamMemberAble, TeamAble):
    """Represents the join leave history for the given practice member. A member can join
    and leave a voice channel more than once during a given practice session. This means we need
    to keep track of a complete history.

    This inherits the following bases:

    - :class:`GuildAble`
    - :class:`TeamMemberAble`
    - :class:`TeamAble`

    Parameters
    ----------
    member: :class:`PracticeMember`
        The member this history belongs to.
    data: :class:`dict`
        The data to initialise this history with. See required
        keys via the attributes section.

    Attributes
    ----------
    member: :class:`PracticeMember`
        The member this history belongs to.
    id: :class:`int`
        The ID of this practice entry.
    joined_at: :class:`datetime.datetime`
        The time the member joined the voice channel.
    left_at: Optional[:class:`datetime.datetime`]
        The time the member left the voice channel. If the member is still in the voice channel
        then this will be ``None``.
    team_id: :class:`int`
        The ID of the team the member is on.
    channel_id: :class:`int`
        The ID of the voice channel this practice is in.
    guild_id: :class:`int`
        The ID of the guild this practice is in.
    """

    def __init__(self, *, member: PracticeMember, data: Dict[str, Any]) -> None:
        self.member: PracticeMember = member

        self.id: int = data['id']
        self.joined_at: datetime.datetime = data['joined_at']
        self.left_at: Optional[datetime.datetime] = data['left_at']
        self.team_id: int = data['team_id']
        self.channel_id: int = data['channel_id']
        self.guild_id: int = data['guild_id']

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    def _get_bot(self) -> FuryBot:
        return self.member.practice.bot

    def _get_member_id(self) -> int:
        return self.member.member_id

    @property
    def total_time(self) -> Optional[datetime.timedelta]:
        """Returns the total time the member was in the voice channel for."""
        if self.left_at is None:
            return None

        return self.left_at - self.joined_at


class PracticeMember(TeamMemberAble, TeamAble):
    """Represents a member that is attending or not attending a practice session.
    A member can be attending or not attending a practice session. If they mark themselves as
    not attending, they will have a reason why.

    This inherits the following bases:

    - :class:`GuildAble`
    - :class:`TeamMemberAble`
    - :class:`TeamAble`

    Parameters
    ----------
    practice: :class:`Practice`
        The practice this member belongs to.
    data: :class:`dict`
        The data to initialise this history with. See required
        keys via the attributes section.

    Attributes
    ----------
    practice: :class:`Practice`
        The practice this member belongs to.
    id: :class:`int`
        The ID of this practice member.
    member_id: :class:`int`
        The Discord ID of the given member.
    practice_id: :class:`int`
        The ID of the practice this member belongs to.
    attending: :class:`bool`
        Whether the member is attending or not. Defaults to ``True`` but
        can be ``False`` if the member has marked themselves as not attending.
    reason: :class:`str`
        The reason the member has marked themselves as not attending. If :attr:`attending`
        is ``False``, this will be :class:`str` 100% of the time.
    """

    def __init__(self, *, practice: Practice, data: Dict[str, Any]) -> None:
        self.practice: Practice = practice

        self.id: int = data['id']
        self.member_id: int = data['member_id']
        self.practice_id: int = data['practice_id']

        self.attending: bool = data['attending']
        self.reason: Optional[str] = data['reason']

        self._history: List[PracticeMemberHistory] = []

    def __eq__(self, __o: object) -> bool:
        try:
            o_member_id = getattr(__o, 'member_id')  # skipcq: PTC-W0034
        except AttributeError:
            return False

        return self.member_id == o_member_id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def __hash__(self) -> int:
        return hash(self.member_id)

    def _get_guild_id(self) -> int:
        return self.practice.guild_id

    def _get_team_id(self) -> int:
        return self.practice.team_id

    def _get_bot(self) -> FuryBot:
        return self.practice.bot

    def _get_member_id(self) -> int:
        return self.member_id

    def add_history(self, data: Dict[str, Any]) -> PracticeMemberHistory:
        practice_member_history = PracticeMemberHistory(member=self, data=data)
        self._history.append(practice_member_history)
        return practice_member_history

    def remove_history(self, history: PracticeMemberHistory) -> None:
        self._history.remove(history)

    @property
    def current_history(self) -> Optional[PracticeMemberHistory]:
        """:class:`PracticeMemberHistory`: Returns the current history element for this member."""
        if not self._history:
            return None

        return self._history[-1]

    @property
    def history(self) -> List[PracticeMemberHistory]:
        """List[:class:`PracticeMemberHistory`]: Returns the history for this member during this practice."""
        return self._history

    @property
    def is_practicing(self) -> bool:
        """Determines if the member is currently in the voice channel for this practice."""
        current_history = self.current_history
        if current_history is None:
            return False

        return current_history.left_at is None

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a Discord mention for this member."""
        return f'<@{self.member_id}>'

    def get_total_practice_time(self) -> datetime.timedelta:
        """:class:`float`: Returns the total time the member has spent in the voice channel for this practice."""
        total_time: datetime.timedelta = datetime.timedelta()
        for history in self._history:
            if history.left_at is None:
                continue

            total_time += history.left_at - history.joined_at

        return total_time

    async def delete(self) -> None:
        """|coro|

        Deletes this member from this practice, deleting their history for this practice as well.
        """
        async with self.practice.bot.safe_connection() as connection:
            await connection.execute("DELETE FROM teams.practice_member WHERE id = $1", self.id)
            await connection.execute(
                "DELETE FROM teams.practice_member_history WHERE member_id = $1 AND practice_id = $2",
                self.member_id,
                self.practice_id,
            )

        # Remove from the practice's cache as well
        self.practice.remove_member(self.member_id)

    async def handle_join(self, *, when: Optional[datetime.datetime] = None) -> PracticeMemberHistory:
        """|coro|

        Will handle the given member joining the voice channel for this practice. This will create a new instance of :class:`PracticeMemberHistory`
        and return it to the caller.

        Parameters
        ----------
        when: Optional[:class:`datetime.datetime`]
            The time the member joined the voice channel. If this is not given, it will default to the current time.

        Returns
        -------
        :class:`PracticeMemberHistory`
            The new history element for this member.
        """
        _log.debug("Handling practice member join, creating new history element. %s", self.member_id)

        async with self.practice.bot.safe_connection() as connection:
            practice_member_history_data = await connection.fetchrow(
                """
                INSERT INTO teams.practice_member_history(
                    joined_at, 
                    team_id, 
                    channel_id, 
                    guild_id, 
                    practice_id, 
                    member_id
                ) 
                VALUES($1, $2, $3, $4, $5, $6) 
                RETURNING *""",
                when,
                self.practice.team_id,
                self.practice.channel_id,
                self.practice.guild_id,
                self.practice_id,
                self.member_id,
            )
            if not practice_member_history_data:
                raise ValueError("Failed to create practice member history.")

            practice_member_history = self.add_history(dict(practice_member_history_data))

        return practice_member_history

    async def handle_leave(self, *, when: Optional[datetime.datetime] = None) -> PracticeMemberHistory:
        """|coro|

        Will handle the current member leaving the given voice channel for this practice. This will edit the current instance of :class:`PracticeMemberHistory`
        and return it to the caller.

        Parameters
        ----------
        when: Optional[:class:`datetime.datetime`]
            The time the member left the voice channel. If this is not given, it will default to the current time.

        Returns
        -------
        :class:`PracticeMemberHistory`
            The updated history element for this member.
        """
        _log.debug("Handling practice member leave, updating current history element. %s", self.member_id)

        current_history = self.current_history
        if current_history is None:
            raise ValueError('Member never joined a voice channel and has no history, but tried to remove history.')

        async with self.practice.bot.safe_connection() as connection:
            await connection.execute(
                "UPDATE teams.practice_member_history SET left_at = $1 WHERE id = $2", when, current_history.id
            )

        current_history.left_at = when

        return current_history


class PracticeStatus(enum.Enum):
    """A practice can have one of two statuses, either it is ongoing or completed.

    A practice will be marked as completed when all members have left the voice channel the practice is
    marked to be in.
    """

    ongoing = 'ongoing'
    completed = 'completed'


class Practice(TeamAble):
    """Represents a practice for a given team.

    A practice can have up to N members and needs to be in a voice channel. The member that starts a practice
    must be in the teams voice channel and will be the only one that can start a practice. There can not be more
    than one practice at a time. The minimum amount of a time for a practice is 10 minutes, any less than that will be
    thrown out automatically.

    This inherits the following bases:

    - :class:`GuildAble`
    - :class:`TeamAble`

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    data: :class:`dict`
        The raw data for this practice. See the attributes below
        for the required keys.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    id: :class:`int`
        The ID of this practice.
    started_at: :class:`datetime.datetime`
        The time this practice was started.
    ended_at: Optional[:class:`datetime.datetime`]
        The time this practice was ended. This will be ``None`` if the practice is still ongoing.
    team_id: :class:`int`
        The ID of the team this practice is for.
    channel_id: :class:`int`
        The ID of the voice channel this practice is in.
    guild_id: :class:`int`
        The ID of the guild this practice is in.
    status: :class:`PracticeStatus`
        The status of this practice.
    message_id: :class:`int`
        The ID of the message that is used to display the current status of the practice
        to the team members.
    view: :class:`PracticeView`
        The persistent view used to display the current status of the practice to the team members.
        Also used to handle the buttons for the practice.
    started_by_id: :class:`int`
        The ID of the member that started this practice.
    """

    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot

        self.id: int = data['id']
        self.started_at: datetime.datetime = data['started_at']
        self.ended_at: Optional[datetime.datetime] = data['ended_at']

        self.team_id: int = data['team_id']

        self.channel_id: int = data['channel_id']
        self.guild_id: int = data['guild_id']
        self.status: PracticeStatus = PracticeStatus(data['status'])

        self.message_id: int = data['message_id']
        self.view: PracticeView = PracticeView(practice=self)
        self.bot.add_view(self.view, message_id=self.message_id)

        self.started_by_id: int = data['started_by_id']

        self._members: Dict[int, PracticeMember] = {}

    def __hash__(self) -> int:
        return hash(self.id)

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    def _get_bot(self) -> FuryBot:
        return self.bot

    # Methods to manage member cache
    def add_member(self, practice_member_data: Dict[str, Any]) -> PracticeMember:
        member = PracticeMember(practice=self, data=practice_member_data)
        self._members[member.member_id] = member
        return member

    def remove_member(self, member_id: int) -> Optional[PracticeMember]:
        self._members.pop(member_id, None)

    @property
    def team(self) -> Optional[Team]:
        """:class:`Team`: The team this practice is for."""
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def members(self) -> List[PracticeMember]:
        """List[:class:`PracticeMember`]: A list of all members that are or are not attending this practice."""
        return list(self._members.values())

    @property
    def attending_members(self) -> List[PracticeMember]:
        """List[:class:`PracticeMember`]: A list of all members that are attending this practice."""
        return [m for m in self.members if m.attending]

    @property
    def excused_members(self) -> List[PracticeMember]:
        """List[:class:`PracticeMember`]: A list of all members that are excused from this practice. These are the members
        that opted-out of this practice and provided a reason."""
        return [m for m in self.members if not m.attending]

    @property
    def missing_members(self) -> List[TeamMember]:
        """List[:class:`TeamMember`]: A list of all members that are missing from this practice. These are the members
        have not yet joined the practice or opted-out of it."""
        team = self.team
        if not team:
            return []

        return [m for m in team.members if m.member_id not in self._members]

    @property
    def started_by(self) -> Optional[PracticeMember]:
        """:class:`PracticeMember`: The member that started this practice."""
        return self.get_member(self.started_by_id)

    @property
    def ongoing(self) -> bool:
        """:class:`bool`: Whether this practice is ongoing or not."""
        return self.status is PracticeStatus.ongoing

    @property
    def duration(self) -> Optional[datetime.timedelta]:
        """Optional[:class:`datetime.timedelta`]: The duration of this practice. This will be ``None`` if the practice has not ended."""
        if not self.ended_at:
            return None

        return self.ended_at - self.started_at

    @property
    def total_points(self) -> Optional[float]:
        """Calculates the total points this practice has generated for the team.

        The formula used in the function gives a bonus of 10% for each additional member in the team,
        in addition to the base score of hours.

        For example, if a team of 2 members practiced for 5 hours, the score would be:

        .. code-block:: python3

            print(practice.total_points) # 5 hours at 2 members
            >>> 7.0

        Returns
        -------
        Optional[:class:`float`]
            The total points this practice has generated for the team.
            This will be ``None`` if the practice has not ended.
        """
        total_time = self.duration
        if not total_time:
            return None

        if len(self.attending_members) == 1:
            return 0

        hours = total_time.total_seconds() / 3600
        return hours * (1 + BONUS_STRENGTH * math.log10(len(self.attending_members)))

    def get_member(self, member_id: int) -> Optional[PracticeMember]:
        """Gets a member from this practice.

        Parameters
        ----------
        member_id: :class:`int`
            The ID of the member to get.

        Returns
        -------
        Optional[:class:`PracticeMember`]
            The member if they are in this practice, otherwise ``None``.
        """
        return self._members.get(member_id)

    def format_start_time(self) -> str:
        """:class:`str`: A formatted string with Discord timestamps representing the start time of this practice."""
        return f'{discord.utils.format_dt(self.started_at, "F")} ({discord.utils.format_dt(self.started_at, "R")})'

    def format_end_time(self) -> Optional[str]:
        """Optional[:class:`str`]: A formatted string with Discord timestamps representing the end time of this practice.
        Will be ``None`` if the practice has not ended."""
        if not self.ended_at:
            return None

        return f'{discord.utils.format_dt(self.ended_at, "F")} ({discord.utils.format_dt(self.ended_at, "R")})'

    def get_total_practice_time(self) -> Optional[datetime.timedelta]:
        """Optional[:class:`datetime.timedelta`]: The total time this practice was. This will be ``None`` if the practice has not ended."""
        if not self.ended_at:
            return None

        return self.ended_at - self.started_at

    async def fetch_end_embed(self) -> discord.Embed:
        """|coro|

        Fetches the embed that is sent when this practice ends.

        Returns
        -------
        :class:`discord.Embed`
        """
        team = self.team
        if not team:
            # This team has been deleted yet the practice has still ended. It's going to fail sending anyways
            # so we can safety return an empty embed here (this should never happen though)
            return discord.Embed()

        started_by = self.started_by and self.started_by.mention or "`<not-found>`"
        embed = team.embed(
            title=f'{team.display_name} Practice Ended.',
            description=f'This practice started by {started_by} has come to an end.\n'
            f'- **Started At**: {self.format_start_time()}\n'
            f'- **Ended At**: {self.format_end_time()}\n',
        )

        practice_members_formatted = '\n'.join(
            [f'{m.mention}: {human_timedelta(m.get_total_practice_time().total_seconds())}' for m in self.attending_members]
        )
        excused_members_formatted = ', '.join([m.mention for m in self.excused_members])

        embed.add_field(
            name='Attended Members',
            value=f'{len(self.attending_members)} members attended this practice session.\n{practice_members_formatted}',
            inline=False,
        )

        if excused_members_formatted:
            embed.add_field(
                name='Excused Members',
                value=f'The following members could not make it to this practice session: {excused_members_formatted}',
                inline=False,
            )

        missing_members = self.missing_members
        if missing_members:
            missing_members_mentions = ', '.join([m.mention for m in missing_members])
            embed.add_field(
                name='Missing Members',
                value=f'The following did not go to the practice and did not mark themselves as excused: {missing_members_mentions}',
            )

        ranking = team.get_practice_rank()
        embed.add_field(
            name='Practice Time Rank',
            value=f'Out of {len(self.bot.get_teams(self.guild_id))} teams, this team is ranked **#{ranking}** in practice time.',
            inline=False,
        )

        return embed

    # Methods for managing members that join and leave the voice channel for the given practice session.
    async def handle_member_unable_to_join(
        self, *, member: Union[discord.Member, discord.User], reason: str
    ) -> PracticeMember:
        """|coro|

        Called when a member is unable to join the voice channel for this practice session. This will create a new :class:`PracticeMember` and
        add it to the cache.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member that is unable to join the voice channel.
        reason: :class:`str`
            The reason the member is unable to join the voice channel.

        Returns
        -------
        :class:`PracticeMember`
            The newly created practice member.
        """
        team = self.team
        if not team:
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        if team.get_member(member.id) is None:
            _log.debug("Member %s is not on the team.", member.id)
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        attending_member = self.get_member(member.id)
        if attending_member is not None:
            # This member has not joined the practice session yet, let's create a new practice member.
            _log.debug("Member %s is already attending.", member.id)
            raise MemberAlreadyInPractice(f'The member {member.id} is already attending practice {self.id}.')

        async with self.bot.safe_connection() as connection:
            practice_member_data = await connection.fetchrow(
                """
                INSERT INTO teams.practice_member (
                    member_id, 
                    practice_id, 
                    attending, 
                    reason
                ) 
                VALUES ($1, $2, $3, $4) 
                RETURNING *""",
                member.id,
                self.id,
                False,
                reason,
            )
            if not practice_member_data:
                raise ValueError("Failed to create practice member.")

        attending_member = self.add_member(dict(practice_member_data))

        await self.view.update_message()
        return attending_member

    async def handle_member_join(
        self, *, member: Union[discord.Member, discord.User], when: Optional[datetime.datetime] = None
    ) -> PracticeMember:
        """|coro|

        Called when a member joins a given practice session. This will create a new :class:`PracticeMember` and
        add it to the cache.

        This function will check to ensure the passed member is on the given team. If they are not, this will
        raise an exception.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member that joined the voice channel.
        channel: :class:`discord.VoiceChannel`
            The channel the member joined to. This will be the :class:`Team`'s voice channel (:attr:`Team.voice_channel`).
        when: Optional[:class:`datetime.datetime`]
            The time the member joined the voice channel. If this is not given, it will default to :func:`discord.utils.utcnow`.

        Returns
        -------
        :class:`PracticeMember`
            The newly created practice member.

        Raises
        ------
        MemberNotOnTeam
            This member is not on the team and can not join the practice session.
        """
        _log.debug("Handling new member join voice channel for practice. %s", member.id)

        when = when or discord.utils.utcnow()

        team = self.team
        if not team:
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        if team.get_member(member.id) is None:
            _log.debug("Member %s is not on the team.", member.id)
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        attending_member = self.get_member(member.id)
        if attending_member is None:
            # This member has not joined the practice session yet, let's create a new practice member.
            _log.debug("Creating new practice member for member %s", member.id)

            async with self.bot.safe_connection() as connection:
                practice_member_data = await connection.fetchrow(
                    "INSERT INTO teams.practice_member (member_id, practice_id) VALUES ($1, $2) RETURNING *",
                    member.id,
                    self.id,
                )
                if not practice_member_data:
                    raise ValueError("Failed to create practice member.")

            attending_member = self.add_member(dict(practice_member_data))
        else:
            # Check if they manually selected not attending.
            if not attending_member.attending:
                # They just joined the voice channel, let's ignore them
                _log.debug("Member %s is not attending practice. ignoring them.", member.id)
                raise MemberNotAttendingPractice(f'The member {member.id} is not attending practice {self.id}.')

        # Let's handle this member joining the practice session. This will create a new history element
        # for the member so we have updated cache.
        await attending_member.handle_join(when=when)

        await self.view.update_message()
        return attending_member

    async def handle_member_leave(self, *, member: discord.Member, when: Optional[datetime.datetime] = None) -> None:
        """|coro|

        Called when a member has left the voice channel and needs to be cleaned up from the cache.

        This will mark the :class:`PracticeMember`'s current :class:`PracticeMemberHistory`'s ``left_at`` and
        update the current embed.
        """
        _log.debug("Handling member leave voice channel")
        when = when or discord.utils.utcnow()

        team = self.team
        if not team:
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        if team.get_member(member.id) is None:
            _log.debug("Member %s is not on the team, can not handle leave.", member.id)
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        team_member = self.get_member(member.id)
        if team_member is None:
            _log.debug("Member %s is not in the practice session, can not handle leave.", member.id)
            raise MemberNotInPractice(f'The member {member.id} is not in the practice session.')

        if not team_member.attending:
            # This member just joined the voice channel and left but isn't attending, ignore them.
            raise MemberNotAttendingPractice(f'The member {member.id} is not attending practice {self.id}.')

        # Remember that members are removed from the cache when they leave, they're simply updated
        await team_member.handle_leave(when=when)

        # Finally update our message to edit the embed.
        await self.view.update_message()

        # We need to check if all members have left the voice channel and if so, we need to mark the practice
        # as completed. Note if one member remains in the voice chat we can end it as well, they'd be alone.
        # We don't need API calls here we can use our cache
        remaining_practicers = [member for member in self.members if member.is_practicing and member != team_member]
        if not remaining_practicers or len(remaining_practicers) == 1:
            # We can mark the practice as completed.

            # If there's one remaining member we need to make sure their history is accurate
            if len(remaining_practicers) == 1:
                remaining = remaining_practicers[0]
                await remaining.handle_leave(when=when)

            await self.end()

    async def end(self) -> None:
        """|coro|

        Ends the practice and marks it as completed. This will send the stats embed
        to the team channel and mention the captain(s) of the team.
        """
        self.status = PracticeStatus.completed
        self.ended_at = discord.utils.utcnow()
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                "UPDATE teams.practice SET status = $1, ended_at = $2 WHERE id = $3",
                self.status.value,
                self.ended_at,
                self.id,
            )

        _log.debug("Practice %s has ended.", self.id)

        embed = await self.fetch_end_embed()

        # NOTE: Add a note for if only one member joins the practice session.
        if len(self.attending_members) == 1:
            embed.insert_field_at(
                0, name='Warning', value='There is only one member that attended this practice session.', inline=False
            )

        # We can only reply to the message if the team text channel is still around.
        # In the case it's not, some muppet has deleted it.
        team = self.team
        team_text_channel = team and team.text_channel
        if not team or not team_text_channel:
            return

        message = await team_text_channel.fetch_message(self.message_id)
        await message.reply(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=team.captain_roles),
            content=', '.join(r.mention for r in team.captain_roles),
        )

    async def delete(self) -> None:
        """|coro|

        Deletes the practice session and removes it from the cache.
        """
        async with self.bot.safe_connection() as connection:
            await connection.execute("DELETE FROM teams.practice WHERE id = $1", self.id)
        # Delete this practice from the bot's cache as well

        self.bot.remove_practice(self.id, self.team_id, self.guild_id)
