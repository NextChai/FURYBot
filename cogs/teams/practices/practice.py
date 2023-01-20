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
import asyncio
import datetime
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import discord

from utils.bases import Guildable, Teamable, TeamMemberable
from utils.time import human_timedelta

from ..errors import MemberNotOnTeam
from .errors import *
from .persistent import PracticeView

if TYPE_CHECKING:
    from bot import FuryBot

    from ..team import Team

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)  # A temporary placeholder until everything is done.


class PracticeMemberHistory(Guildable, TeamMemberable, Teamable):
    """Represents the join leave history for the given practice member. A member can join
    and leave a voice channel more than once during a given practice session. This means we need
    to keep track of a complete history.

    This inherits the following bases:

    - :class:`Guildable`
    - :class:`TeamMemberable`
    - :class:`Teamable`

    NOTE: Add attrs
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


class PracticeMember(Guildable, TeamMemberable, Teamable):
    """Represents a member that is attending or not attending a practice session.
    A member can be attending or not attending a practice session. If they mark themselves as
    not attending, they will have a reason why.

    This inherits the following bases:

    - :class:`Guildable`
    - :class:`TeamMemberable`
    - :class:`Teamable`

    NOTE: Add attrs
    """

    def __init__(self, *, practice: Practice, data: Dict[str, Any]) -> None:
        self.practice: Practice = practice

        self.id: int = data['id']
        self.member_id: int = data['member_id']
        self.practice_id: int = data['practice_id']

        self.attending: bool = data['attending']
        self.reason: Optional[str] = data['reason']

        self._history: List[PracticeMemberHistory] = []
        self._history_lock: asyncio.Lock = asyncio.Lock()  # Don't want to be creating and removing history at the same time.

    def __eq__(self, __o: object) -> bool:
        try:
            o_member_id = getattr(__o, 'member_id')
        except AttributeError:
            return False

        return self.member_id == o_member_id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def _get_guild_id(self) -> int:
        return self.practice.guild_id

    def _get_team_id(self) -> int:
        return self.practice.team_id

    def _get_bot(self) -> FuryBot:
        return self.practice.bot

    def _get_member_id(self) -> int:
        return self.member_id

    def _add_history(self, data: Dict[str, Any]) -> PracticeMemberHistory:
        practice_member_history = PracticeMemberHistory(member=self, data=data)
        self._history.append(practice_member_history)
        return practice_member_history

    def _remove_history(self, history: PracticeMemberHistory) -> None:
        self._history.remove(history)

    @property
    def current_history(self) -> Optional[PracticeMemberHistory]:
        """:class:`PracticeMemberHistory`: Returns the current history element for this member."""
        if not self._history:
            return None

        return self._history[-1]

    @property
    def is_practicing(self) -> bool:
        current_history = self.current_history
        if current_history is None:
            return False

        return current_history.left_at is None

    @property
    def mention(self) -> str:
        return f'<@{self.member_id}>'

    def get_total_practice_time(self) -> datetime.timedelta:
        """:class:`float`: Returns the total time the member has spent in the voice channel for this practice."""
        total_time: datetime.timedelta = datetime.timedelta()
        for history in self._history:
            if history.left_at is None:
                continue

            total_time += history.left_at - history.joined_at

        return total_time

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

        async with self._history_lock:
            async with self.practice.bot.safe_connection() as connection:
                practice_member_history_data = await connection.fetchrow(
                    "INSERT INTO teams.practice_member_history(joined_at, team_id, channel_id, guild_id, practice_id, member_id) VALUES($1, $2, $3, $4, $5, $6) RETURNING *",
                    when,
                    self.practice.team_id,
                    self.practice.channel_id,
                    self.practice.guild_id,
                    self.practice.id,
                    self.member_id,
                )
                assert practice_member_history_data

            practice_member_history = self._add_history(dict(practice_member_history_data))

        return practice_member_history

    async def handle_leave(self, *, when: Optional[datetime.datetime] = None) -> PracticeMemberHistory:
        """|coro|

        Will handle the current member leaving the given voice channel for this pracitce. This will edit the current instance of :class:`PracticeMemberHistory`
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

        async with self._history_lock:
            current_history = self.current_history
            assert current_history  # This can't get called unless this is not None

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


class Practice(Guildable, Teamable):
    """Represents a practice for a given team.

    A practice can have up to N members and needs to be in a voice channel. The member that starts a practice
    must be in the teams voice channel and will be the only one that can start a practice. There can not be more
    than one practice at a time. The minimum amount of a time for a practice is 10 minutes, any less than that will be
    thrown out automaitcally.

    This inherits the following bases:

    - :class:`Guildable`
    - :class:`Teamable`

    NOTE: Add attrs
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

    def _get_guild_id(self) -> int:
        return self.guild_id

    def _get_team_id(self) -> int:
        return self.team_id

    def _get_bot(self) -> FuryBot:
        return self.bot

    # Methods to manage member cache
    def _add_member(self, practice_member_data: Dict[str, Any]) -> PracticeMember:
        member = PracticeMember(practice=self, data=practice_member_data)
        self._members[member.member_id] = member
        return member

    def _remove_member(self, member_id: int) -> Optional[PracticeMember]:
        self._members.pop(member_id, None)

    @property
    def team(self) -> Team:
        return self.bot.team_cache[self.team_id]

    @property
    def members(self) -> List[PracticeMember]:
        return list(self._members.values())

    @property
    def started_by(self) -> PracticeMember:
        member = self.get_member(self.started_by_id)
        return cast(PracticeMember, member)

    @property
    def ongoing(self) -> bool:
        return self.status is PracticeStatus.ongoing

    def get_member(self, member_id: int) -> Optional[PracticeMember]:
        return self._members.get(member_id)

    def format_start_time(self) -> str:
        return f'{discord.utils.format_dt(self.started_at, "F")} ({discord.utils.format_dt(self.started_at, "R")})'

    def format_end_time(self) -> Optional[str]:
        if not self.ended_at:
            return None

        return f'{discord.utils.format_dt(self.ended_at, "F")} ({discord.utils.format_dt(self.ended_at, "R")})'

    def get_total_practice_time(self) -> Optional[datetime.timedelta]:
        if not self.ended_at:
            return None

        return self.ended_at - self.started_at

    # Methods for managing members that join and leave the voice channel for the given practice session.
    async def handle_member_unable_to_join(self, *, member: discord.Member, reason: str) -> PracticeMember:
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
        if self.team.get_member(member.id) is None:
            _log.debug("Member %s is not on the team.", member.id)
            raise MemberNotOnTeam(f'The member {member.id} is not on the team {self.team_id}, can not join practice.')

        attending_member = self.get_member(member.id)
        if attending_member is not None:
            # This member has not joined the practice session yet, let's create a new practice member.
            _log.debug("Member %s is already attending.", member.id)
            raise MemberAlreadyInPractice(f'The member {member.id} is already attending practice {self.id}.')

        async with self.bot.safe_connection() as connection:
            practice_member_data = await connection.fetchrow(
                "INSERT INTO teams.practice_member (member_id, practice_id, attending, reason) VALUES ($1, $2, $3, $4) RETURNING *",
                member.id,
                self.id,
                False,
                reason,
            )
            assert practice_member_data

        attending_member = self._add_member(dict(practice_member_data))

        await self.view.update_message()
        return attending_member

    async def handle_member_join(
        self, *, member: discord.Member, when: Optional[datetime.datetime] = None
    ) -> PracticeMember:
        """|coro|

        Called when a member joins a given pracice session. This will create a new :class:`PracticeMember` and
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

        if self.team.get_member(member.id) is None:
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
                assert practice_member_data

            attending_member = self._add_member(dict(practice_member_data))
        else:
            # Check if they manually selected not attending.
            if not attending_member.attending:
                # They just joined the voice channel, let's ignore them
                # TODO: Maybe edit this?
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

        if self.team.get_member(member.id) is None:
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
        # as completed.
        # We don't need API calls here we can use our cache
        if all(not member.is_practicing for member in self.members):
            # We can mark the practice as completed.
            await self.end()

    async def end(self) -> None:
        """|coro|

        Ends the practice and marks it as completed. This will send the stats embed
        to the team channel and mention the captain(s) of the team.
        """
        # NOTE: Impl
        # NOTE: Keep track of members who DIDN't show up.

        # Edit this in the DB and edit our status
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

        embed = self.bot.Embed(
            title=f'{self.team.display_name} Practice Ended.',
            description=f'This practice started by {self.started_by.mention} has come to an end.\n '
            f'- **Started At**: {self.format_start_time()}\n'
            f'- **Ended At**: {self.format_end_time()}\n',
        )

        practice_members_formatted = '\n'.join(
            [
                f'{m.mention}: {human_timedelta(m.get_total_practice_time().total_seconds())}'
                for m in self.members
                if m.attending
            ]
        )
        excused_members_fornmatted = ', '.join([m.mention for m in self.members if not m.attending])

        embed.add_field(
            name='Attended Members',
            value=f'{len([m for m in self.members if m.attending])} members attended this practice session.\n{practice_members_formatted}',
            inline=False,
        )

        if excused_members_fornmatted:
            embed.add_field(
                name='Excused Members',
                value=f'The following members could not make it to this practice session: {excused_members_fornmatted}',
                inline=False,
            )

        ranking = await self.team.fetch_practice_rank()
        embed.add_field(
            name='Practice Time Rank',
            value=f'Out of {len(self.bot.team_cache)} teams, your team is ranked **#{ranking}** in practice time.',
            inline=False,
        )

        message = await self.team.text_channel.fetch_message(self.message_id)
        await message.reply(embed=embed)
