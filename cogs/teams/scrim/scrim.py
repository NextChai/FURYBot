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
from typing import TYPE_CHECKING, List, Optional

import discord

if TYPE_CHECKING:
    from bot import FuryBot

    from ..team import Team, TeamMember


# Persistent views for team scrim confirmation from both
class ScrimStatus(enum.Enum):
    """
    An enum to represent the status of a scrim.

    pending_away: The away team has not yet confirmed the scrim.
    scheduled: The scrim has been scheduled.
    pending_host: The scrim is pending confirmation from the host.
    """

    pending_away = 'pending_away'
    scheduled = 'scheduled'
    pending_host = 'pending_host'


@dataclasses.dataclass(init=True, repr=True, eq=True)
class Scrim:
    """Represents a scrim between two teams.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    id: :class:`int`
        The id of the scrim.
    guild_id: :class:`int`
        The id of the guild the scrim is in.
    creator_id: :class:`int`
        The id of the user who created the scrim.
    per_team: :class:`int`
        The number of players per team.
    home_id: :class:`int`
        The id of the home team.
    away_id: :class:`int`
        The id of the away team.
    home_message_id: :class:`int`
        The id of the message in the home team's text channel.
    away_message_id: :class:`int`
        The id of the message in the away team's text channel.
    status: :class:`ScrimStatus`
        The status of the scrim.
    home_voter_ids: List[:class:`int`]
        The ids of the users who have voted for the home team.
    away_voter_ids: List[:class:`int`]
        The ids of the users who have voted for the away team.
    away_confirm_anyways_voter_ids: List[:class:`int`]
        The ids of the users who have voted to confirm the scrim anyways.
        Defaults to an empty list.
    away_confirm_anyways_message_id: Optional[:class:`int`]
        The id of the message in the away team's text channel.
    scheduled_for: :class:`datetime.datetime`
        The time the scrim is scheduled for.
    scrim_chat_id: Optional[:class:`int`]
        The id of the scrim chat.
    """

    bot: FuryBot
    id: int
    guild_id: int
    creator_id: int
    per_team: int
    home_id: int
    away_id: int
    home_message_id: int
    away_message_id: Optional[int]
    status: ScrimStatus
    home_voter_ids: List[int]
    away_voter_ids: List[int]
    away_confirm_anyways_voter_ids: List[int]
    away_confirm_anyways_message_id: Optional[int]
    scheduled_for: datetime.datetime
    scrim_chat_id: Optional[int]

    @property
    def home_team(self) -> Team:
        """:class:`Team`: The home team."""
        return self.bot.team_cache[self.home_id]

    @property
    def away_team(self) -> Team:
        """:class:`Team`: The away team."""
        return self.bot.team_cache[self.away_id]

    @property
    def guild(self) -> Optional[discord.Guild]:
        """Optional[:class:`discord.Guild`]: The guild the scrim is in. Can be None if the guild is not found."""
        return self.bot.get_guild(self.guild_id)

    @property
    def home_voters(self) -> List[TeamMember]:
        """Get a list of the home team's voters.

        Returns
        --------
        List[:class:`TeamMember`]
        """
        members = self.home_team.team_members
        return [member for (member_id, member) in members.items() if member_id in self.home_voter_ids]

    @property
    def away_voters(self) -> List[TeamMember]:
        """Get a list of the away team's voters.

        Returns
        --------
        List[:class:`TeamMember`]
        """
        members = self.away_team.team_members
        return [member for (member_id, member) in members.items() if member_id in self.away_voter_ids]

    @property
    def away_confirm_anyways_voters(self) -> List[TeamMember]:
        """Get a list of the away team's voters for confirming the scrim anyways.

        Returns
        -------
        List[:class:`TeamMember`]
        """
        members = self.away_team.team_members
        return [member for (member_id, member) in members.items() if member_id in self.away_confirm_anyways_voter_ids]

    @property
    def home_all_voted(self) -> bool:
        """:class:`bool`: Whether the home team has all voted."""
        return len(self.home_voter_ids) >= self.per_team

    @property
    def away_all_voted(self) -> bool:
        """:class:`bool`: Whether the away team has all voted."""
        return len(self.away_voter_ids) >= self.per_team

    def scheduled_for_formatted(self) -> str:
        """:class:`str`: The time the scrim is scheduled for in a human readable format."""
        return f'{discord.utils.format_dt(self.scheduled_for, "F")} ({discord.utils.format_dt(self.scheduled_for, "R")})'

    async def home_message(self) -> discord.Message:
        """|coro|

        Returns
        --------
        :class:`discord.Message`
            The message in the home team's text channel."""
        channel = self.home_team.text_channel
        return await channel.fetch_message(self.home_message_id)

    async def away_message(self) -> Optional[discord.Message]:
        """|coro|

        Returns
        --------
        Optional[:class:`discord.Message`]
            The message in the away team's text channel. ``None`` if there is no message in the away channel.
        """
        if not self.away_message_id:
            return None

        channel = self.away_team.text_channel
        return await channel.fetch_message(self.away_message_id)

    async def change_status(self, status: ScrimStatus, /) -> None:
        """|coro|

        Change the status of the scrim.

        Parameters
        ----------
        scrim: :class:`ScrimStatus`
            The new status of the scrim.
        """
        self.status = status

        async with self.bot.safe_connection() as connection:
            await connection.execute('UPDATE teams.scrims SET status = $1 WHERE id = $2', status.value, self.id)

    async def add_vote(self, member_id: int, team_id: int) -> None:
        """|coro|

        Add a vote to the scrim.

        Parameters
        ----------
        member_id: :class:`int`
            The ID of the member who you want to add.
        team_id: :class:`int`
            The ID of the team to cast the vote to.

        Raises
        ------
        ValueError
            The member has already voted.
        """
        if team_id == self.home_id:
            if member_id in self.home_voter_ids:
                raise ValueError('Member has already voted.')

            self.home_voter_ids.append(member_id)
        elif team_id == self.away_id:
            if member_id in self.away_voter_ids:
                raise ValueError('Member has already voted.')

            self.away_voter_ids.append(member_id)
        else:
            raise ValueError(f'Team with id {team_id} is not valid for this scrim.')

        column = 'home_voter_ids' if team_id == self.home_id else 'away_voter_ids'
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                f'UPADTE teams.scrims SET {column} = array_append({column}, $1) WHERE id = $2', member_id, self.id
            )

    async def remove_vote(self, member_id: int, team_id: int) -> None:
        """|coro|

        Remove a vote from the scrim.

        Parameters
        ----------
        member_id: :class:`int`
            The ID of the member who you want to remove.
        team_id: :class:`int`
            The ID of the team to remove the vote from.

        Raises
        ------
        ValueError
            The member has not voted.
        """
        if team_id == self.home_id:
            if member_id not in self.home_voter_ids:
                raise ValueError('Member has not voted.')

            self.home_voter_ids.remove(member_id)
        elif team_id == self.away_id:
            if member_id not in self.away_voter_ids:
                raise ValueError('Member has not voted.')

            self.away_voter_ids.remove(member_id)
        else:
            raise ValueError(f'Team with id {team_id} is not valid for this scrim.')

        column = 'home_voter_ids' if team_id == self.home_id else 'away_voter_ids'
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                f'UPADTE teams.scrims SET {column} = array_remove({column}, $1) WHERE id = $2', member_id, self.id
            )

    async def reschedle(self) -> None:
        # NOTE: Maybe restart the voting for the other team as they'll need
        # to all confirm.
        ...
