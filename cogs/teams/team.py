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

import dataclasses
import datetime
import enum
import logging
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, Union

import discord

from utils import RUNNING_DEVELOPMENT, QueryBuilder, human_join

from .errors import TeamNotFound

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot

    from .practices import Practice
    from .scrims import Scrim


MISSING = discord.utils.MISSING

_log = logging.getLogger(__name__)
if RUNNING_DEVELOPMENT:
    _log.setLevel(logging.DEBUG)


@dataclasses.dataclass(init=True, repr=True)
class TeamMember:
    """Represents a member of a team.

    Parameters
    Attributes
    -----------
    bot: :class:`FuryBot`
        The bot instance.
    team_id: :class:`int`
        The team ID.
    member_id: :class:`int`
        The member ID.
    guild_id: :class:`int`
        The ID of the guild that this team member is in.
    is_sub: :class:`bool`
        Whether the member is a sub or not.
    """

    def __init__(self, bot: FuryBot, *, guild_id: int, team_id: int, member_id: int, is_sub: bool) -> None:
        self.bot: FuryBot = bot
        self.team_id: int = team_id
        self.member_id: int = member_id
        self.guild_id: int = guild_id
        self.is_sub: bool = is_sub

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.member_id == __o.member_id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def __hash__(self) -> int:
        return hash(self.member_id)

    @property
    def team(self) -> Optional[Team]:
        """:class:`Team`: The team that this member is on."""
        team = self.bot.get_team(self.team_id, guild_id=self.guild_id)
        return team

    @property
    def discord_member(self) -> Optional[discord.Member]:
        """Optional[:class:`discord.Member`]: A Discord member object."""
        guild = self.team and self.team.guild
        return guild and guild.get_member(self.member_id)

    @property
    def mention(self) -> str:
        """:class:`str`: A mention of the member."""
        return f"<@{self.member_id}>"

    async def remove_from_team(self) -> None:
        """|coro|

        Removes the member from the team.
        """
        team = self.team
        if team is None:
            return

        return await team.remove_team_member(self)

    async def demote(self) -> None:
        """|coro|

        A method used to demote the member from the main roster to a sub on the team.

        Raises
        ------
        Exception
            The member is already a sub.
        """
        team = self.team
        if not team:
            # TODO: Proper exception.
            raise Exception('Team has been deleted.')

        if self.is_sub:
            raise Exception("Can not demote a sub.")

        self.is_sub = True
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                "UPDATE teams.members SET is_sub = True WHERE team_id = $1 AND member_id = $2",
                team.id,
                self.member_id,
            )

    async def promote(self) -> None:
        """|coro|

        A method used to promote a member on the team from a sub onto the main roster.

        Raises
        ------
        Exception
            The member is already on the main roster.
        """
        team = self.team
        if not team:
            raise Exception('Team has been deleted.')

        if not self.is_sub:
            raise Exception("Can not promote a player on the main roster.")

        self.is_sub = False

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                "UPDATE teams.members SET is_sub = False WHERE team_id = $1 AND member_id = $2",
                team.id,
                self.member_id,
            )

    async def fetch_discord_member(self) -> Optional[discord.Member]:
        """|coro|

        A method to fetch the :class:`discord.Member` represented by this
        :class:`TeamMember`.

        Raises
        ------
        Exception
            The guild was not found.
        """
        team = self.team
        if not team:
            return None

        guild = team.guild
        if not guild:
            return None

        try:
            await guild.fetch_member(self.member_id)
        except discord.NotFound:
            # This member has been removed from the guild, we can't fetch them.
            # Remove them from the team as well.
            await team.remove_team_member(self)
            return None

    async def getch_discord_member(self) -> Optional[discord.Member]:
        return self.discord_member or await self.fetch_discord_member()


class CaptainType(enum.Enum):
    role = 'role'
    user = 'user'

    @classmethod
    def from_cls(cls: Type[CaptainType], __type: Type[Any], /) -> CaptainType:
        if __type is discord.Role:
            return cls.role

        return cls.user

    def to_cls(self) -> Type[Any]:
        if self is self.role:
            return discord.Role

        return discord.Member


class TeamCaptains:
    """Denotes the captains of a given team."""

    def __init__(self, bot: FuryBot, *, guild_id: int, team_id: int, captain_id: int, captain_type: str) -> None:
        self.team_id: int = team_id
        self.captain_id: int = captain_id
        self.captain_type: CaptainType = CaptainType(captain_type)
        self.guild_id: int = guild_id
        self.bot = bot

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def team(self) -> Optional[Team]:
        return self.bot.get_team(self.team_id, guild_id=self.guild_id)

    @property
    def mention(self) -> str:
        if self.captain_type is CaptainType.role:
            return f"<@&{self.captain_id}>"

        return f"<@{self.captain_id}>"

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                DELETE FROM teams.captains
                WHERE team_id = $1
                AND captain_id = $2
                ''',
                self.team_id,
                self.captain_id,
            )

    async def getch(self) -> Optional[Union[discord.Member, discord.Role]]:
        guild = self.guild
        if not guild:
            return None

        if self.captain_type is CaptainType.role:
            return guild.get_role(self.captain_id)

        member = guild.get_member(self.captain_id)
        if member:
            return member

        try:
            return await guild.fetch_member(self.captain_id)
        except discord.NotFound:
            # This member has been removed from the guild, we can't fetch them.
            # Remove them from the team as well.
            self.bot.create_task(self.delete())
            return None


@dataclasses.dataclass(init=True, repr=True, eq=True)
class Team:
    """Represents a :class:`Team` which holds members, scrims,
    captains, and much more.

    Parameters
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    id: :class:`int`
        The team ID.
    guild_id: :class:`int`
        The id of the guild this team is bound to.
    category_channel_id: :class:`int`
        Each team has its own category, this is the ID
        of the teams category.
    text_channel_id: :class:`int`
        Each team has its own text channel, this is the ID
        of the teams text channel.
    voice_channel_id: :class:`int`
        Each team has its own voice channel, this is the ID
        of the teams voice channel.
    name: :class:`str`
        The name of the team.
    captain_ids: List[:class:`int`]
        A team always has a captain. A captain can be either
        a role or one specific member.
    extra_channel_ids: List[:class:`int`]
        Any additional channel IDS the team may have.
    team_members: Dict[:class:`int`, :class:`TeamMember`]
        A mapping of team member id to their respective team member objects.
    """

    bot: FuryBot
    id: int
    guild_id: int
    category_channel_id: int
    text_channel_id: int
    voice_channel_id: int
    name: str
    extra_channel_ids: List[int]
    team_members: Dict[int, TeamMember]
    nickname: Optional[str]
    description: Optional[str]
    logo: Optional[str]
    captains: Dict[int, TeamCaptains] = dataclasses.field(default_factory=dict)

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.id == __o.id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def from_channel(cls, channel_id: int, guild_id: int, /, *, bot: FuryBot) -> Team:
        """
        Get a team from one of its channel ids.

        Parameters
        ----------
        channel_id: :class:`int`
            The ID of the channel to use to fetch.
        guild_id: :class:`int`
            The ID of the guild this team is in.
        bot: :class:`FuryBot`
            The bot instance.

        Returns
        -------
        :class:`Team`
            The team found frm the given category id.

        Raises
        -------
        TeamNotFound
            A team belonging to the channel was not found.
        """
        teams = bot.get_teams(guild_id)
        for team in teams:
            if team.has_channel(channel_id):
                return team

        raise TeamNotFound("No team with that channel exists.")

    @classmethod
    def from_raw(
        cls: Type[Team],
        team_data: Dict[str, Any],
        member_data: List[Dict[str, Any]],
        captain_data: List[Dict[str, Any]],
        /,
        *,
        bot: FuryBot,
    ) -> Team:
        guild_id = team_data['guild_id']
        members = {entry["member_id"]: TeamMember(bot, guild_id=guild_id, **entry) for entry in member_data}
        captains = {entry['captain_id']: TeamCaptains(bot, guild_id=guild_id, **entry) for entry in captain_data}

        team = cls(bot, **dict(team_data), team_members=members, captains=captains)
        bot.add_team(team)
        return team

    @classmethod
    async def create(cls: Type[Team], name: str, /, *, guild: discord.Guild, bot: FuryBot) -> Team:
        """|coro|

        Used to create a new team.

        Parameters
        ----------
        name: :class:`str`
            The name of the team.
        guild: :class:`discord.Guild`
            The guild the team is being created in.
        bot: :class:`FuryBot`
            The bot instance.
        """
        category = await guild.create_category(
            name=name,
            overwrites={guild.default_role: discord.PermissionOverwrite(read_messages=False)},
        )
        text_channel = await guild.create_text_channel(name="team-chat", category=category)
        voice_channel = await guild.create_voice_channel(name="Team Voice", category=category)

        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                "INSERT INTO teams.settings (guild_id, category_channel_id, text_channel_id, voice_channel_id, name) "
                "VALUES($1, $2, $3, $4, $5) RETURNING *",
                guild.id,
                category.id,
                text_channel.id,
                voice_channel.id,
                name,
            )

            if not data:
                # Something wrong with our query or the database
                raise Exception("Failed to create a new team.")

        team = cls(bot, **dict(data), team_members={})
        bot.add_team(team)

        return team

    @property
    def guild(self) -> Optional[discord.Guild]:
        """:class:`discord.Guild`: The guild this team is bound to."""
        return self.bot.get_guild(self.guild_id)

    @property
    def members(self) -> List[TeamMember]:
        """List[:class:`TeamMember`]: A list of all team members."""
        return list(self.team_members.values())

    @property
    def main_roster(self) -> List[TeamMember]:
        """List[:class:`TeamMember`]: A list of all team members that are not a sub."""
        return [member for member in self.members if not member.is_sub]

    @property
    def sub_roster(self) -> List[TeamMember]:
        """List[:class:`TeamMember`]: A list of all team members that are a sub."""
        return [member for member in self.members if member.is_sub]

    @property
    def text_channel(self) -> Optional[discord.TextChannel]:
        """:class:`discord.TextChannel`: The text channel this team is bound to."""
        guild = self.guild
        if not guild:
            return None

        channel = guild.get_channel(self.text_channel_id)
        if not channel:
            return None

        if not isinstance(channel, discord.TextChannel):
            raise Exception("Text channel is not a text channel.")

        return channel

    @property
    def voice_channel(self) -> Optional[discord.VoiceChannel]:
        """:class:`discord.VoiceChannel`: The voice channel this team is bound to."""
        guild = self.guild
        if not guild:
            return None

        channel = guild.get_channel(self.voice_channel_id)
        if not channel:
            return None

        if not isinstance(channel, discord.VoiceChannel):
            raise Exception("Voice channel is not a voice channel.")

        return channel

    @property
    def category_channel(self) -> Optional[discord.CategoryChannel]:
        """:class:`discord.CategoryChannel`: The category channel this team is bound to."""
        guild = self.guild
        if not guild:
            raise Exception("Guild not found.")

        channel = guild.get_channel(self.category_channel_id)
        if not channel:
            return None

        if not isinstance(channel, discord.CategoryChannel):
            raise Exception("Category channel is not a category channel.")

        return channel

    @property
    def extra_channels(self) -> List[discord.abc.GuildChannel]:
        """List[:class:`discord.abc.GuildChannel`]: A list of all extra channels this team has."""
        guild = self.guild
        if not guild:
            return []

        channels: List[discord.abc.GuildChannel] = []
        for channel_id in self.extra_channel_ids:
            channel = guild.get_channel(channel_id)
            if channel:
                channels.append(channel)

        return channels

    @property
    def scrims(self) -> List[Scrim]:
        """List[:class:`Scrim`]: A list of all scrims this team has."""
        return self.bot.get_scrims_for(self.id, self.guild_id)

    @property
    def practices(self) -> List[Practice]:
        """List[:class:`Practice`]: A list of all practices this team has."""
        return self.bot.get_practices_for(self.id, self.guild_id)

    @property
    def ongoing_practice(self) -> Optional[Practice]:
        """Optional[:class:`Practice`]: The ongoing practice for this team."""
        return discord.utils.find(lambda practice: practice.ongoing, self.practices)

    @property
    def display_name(self) -> str:
        """:class:`str`: The display name for this team."""
        return f'{self.name} {f"({self.nickname})" if self.nickname else ""}'.strip()

    @property
    def total_points(self) -> float:
        """:class:`float`: The total points for this team based on their practices."""
        practice_points = [points for practice in self.practices if (points := practice.total_points)]
        if not practice_points:
            return 0

        return sum(practice_points)

    def mention_members(self, delimiter: str = ", ") -> str:
        """Mentions all the members in this team.

        Parameters
        ----------
        delimiter: :class:`str`
            The delimiter to use when joining the mentions.

        Returns
        -------
        :class:`str`
            The mentions.
        """
        return human_join((member.mention for member in self.members), delimiter=delimiter)

    def embed(
        self,
        *,
        title: Optional[Any] = None,
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
    ) -> discord.Embed:
        """Creates and standard embed for ths team.

        Parameters
        ----------
        title: :class:`str`
            The title of the embed.
        url: :class:`str`
            The url of the embed.
        description: :class:`str`
            The description of the embed.
        author: Union[:class:`discord.User`, :class:`discord.Member`]
            The author of the embed.
        """
        embed = self.bot.Embed(title=title, description=description, url=url, author=author)

        if author is None:
            embed.set_thumbnail(url=self.logo)
            embed.set_author(name=self.display_name, icon_url=self.logo, url=self.logo)

        embed.set_footer(text=f"Team ID: {self.id}")

        return embed

    def has_channel(self, channel_id: int, /) -> bool:
        """Determines if a channel is bound to this team.

        Parameters
        ----------
        channel_id: :class:`int`
            The channel ID to check.

        Returns
        -------
        :class:`bool`
        """
        return channel_id in [self.category_channel_id, self.text_channel_id, self.voice_channel_id] + self.extra_channel_ids

    def get_member(self, member_id: int, /) -> Optional[TeamMember]:
        """Gets a member from this team based upon the given ID.

        Parameters
        ----------
        member_id: :class:`int`
            The member ID to get.

        Returns
        -------
        Optional[:class:`TeamMember`]
            The member if found, otherwise ``None``.
        """
        return self.team_members.get(member_id)

    def get_practice_streak(self) -> int:
        """The current practice streak for this team. This is the number of practices in a row that have
        been completed.

        Returns
        -------
        :class:`int`
            The practice streak.
        """
        streak = 0
        for i, practice in enumerate(self.practices):
            if i == 0:
                continue

            ended_at = practice.ended_at
            if ended_at is None:  # This practice is still going, we'll include it.
                streak += 1
                continue

            previous_ended_at = self.practices[i - 1].ended_at
            if previous_ended_at is None:  # This should't happen but if it does, we'll just skip it.
                continue

            if (ended_at - previous_ended_at).days < 8:
                streak += 1
            else:
                streak = 0

        return streak

    def get_total_practice_time(self) -> datetime.timedelta:
        """Gets the total practice time for this team.

        Returns
        -------
        :class:`datetime.timedelta`
            The total practice time.
        """
        total_time = datetime.timedelta()

        for practice in self.practices:
            prac_time = practice.get_total_practice_time()
            if prac_time is not None:
                total_time += prac_time

        return total_time

    def rank_member_practice_times(self) -> List[Tuple[TeamMember, datetime.timedelta]]:
        """Ranks the members of this team based upon their practice times.

        Returns
        -------
        List[Tuple[:class:`TeamMember`, :class:`datetime.timedelta`]]
            A list of tuples containing the member and their practice time.
        """
        member_times: Dict[TeamMember, datetime.timedelta] = {}

        for practice in self.practices:
            if practice.ongoing:  # Don't count ongoing practices
                continue

            practice_time = practice.get_total_practice_time()
            if not practice_time:  # This should never happen
                continue

            for member in practice.members:
                team_member = self.get_member(member.member_id)
                if team_member is None:
                    continue

                # Setdefault wont let us use += so we have to do this
                if team_member not in member_times:
                    member_times[team_member] = member.get_total_practice_time()
                else:
                    member_times[team_member] += member.get_total_practice_time()

        return sorted(member_times.items(), key=lambda item: item[1], reverse=True)

    def rank_member_absences(self) -> List[Tuple[TeamMember, int]]:
        """Ranks the members on their team based on their absences for team practices.

        Returns
        -------
        List[Tuple[:class:`TeamMember`, :class:`int`]]
            A list of tuples containing the member and their absence count.
        """
        member_absences: Counter[TeamMember] = Counter()

        for practice in self.practices:
            for member in practice.missing_members:
                member_absences[member] += 1

        return member_absences.most_common()

    def get_practice_rank(self) -> int:
        """|coro|

        Gets the rank of this team in the practice leaderboard.

        Returns
        -------
        :class:`int`
            The rank of the team in the practice leaderboard.
        """
        # Count up all the teams scores, rank them, then get the rank of the team we're looking for
        teams = self.bot.get_teams(self.guild_id)
        team_scores = [(team, team.total_points) for team in teams]
        return sorted(team_scores, key=lambda item: item[1], reverse=True).index((self, self.total_points)) + 1

    # Captain related methods
    def has_captain(self, target_id: int, /) -> bool:
        return bool(self.captains.get(target_id))

    async def remove_captain(self, target_id: int, /) -> None:
        if not self.captains.pop(target_id, None):
            return None

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                '''
                DELETE FROM teams.captains
                WHERE team_id = $1
                AND captain_id = $2
                ''',
                self.id,
                target_id,
            )

        await self.sync()

    async def add_captain(self, target_id: int, captain_type: CaptainType, /) -> TeamCaptains:
        if self.has_captain(target_id):
            # Simply return the existing captain
            _log.debug('Captain %s exists, returning.', target_id)
            return self.captains[target_id]

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                '''
                INSERT INTO teams.captains (team_id, captain_id, captain_type)
                VALUES($1, $2, $3)
                RETURNING *
                ''',
                self.id,
                target_id,
                captain_type.value,
            )

            if not data:
                raise Exception("Failed to add a new captain to the team.")

        captain = TeamCaptains(self.bot, guild_id=self.guild_id, **dict(data))
        self.captains[captain.captain_id] = captain

        await self.sync()
        return captain

    async def channel_overwrites(
        self,
    ) -> Dict[discord.Object, discord.PermissionOverwrite]:
        """Dict[Union[:class:`discord.Role`, :class:`discord.Member`], :class:`discord.PermissionOverwrite`]:
        The channel overwrites for this team.
        """
        guild = self.guild
        if not guild:
            return {}

        overwrites: Dict[discord.Object, discord.PermissionOverwrite] = {
            discord.Object(guild.default_role.id, type=discord.Role): discord.PermissionOverwrite(read_messages=False)
        }

        for team_member in self.team_members.values():
            discord_member = await team_member.getch_discord_member()
            if discord_member:
                overwrites[discord.Object(discord_member.id, type=discord.Member)] = discord.PermissionOverwrite(
                    view_channel=True
                )

        for captain in self.captains.values():
            overwrites[discord.Object(captain.captain_id, type=captain.captain_type.to_cls())] = discord.PermissionOverwrite(
                view_channel=True
            )

        return overwrites

    async def sync(self) -> None:
        """|coro|

        Syncs the team's channels with the data in the team.
        """
        overwrites = await self.channel_overwrites()

        if self.category_channel:
            await self.category_channel.edit(overwrites=overwrites, name=self.name, reason='Syncing team channels.')

        if self.text_channel:
            _log.debug('Syncing text channel %s for team %s', self.text_channel.id, self.id)
            await self.text_channel.edit(sync_permissions=True, name='team-chat', reason='Syncing team channels.')

        if self.voice_channel:
            _log.debug('Syncing voice channel %s for team %s', self.voice_channel.id, self.id)
            await self.voice_channel.edit(sync_permissions=True, name='Voice Chat', reason='Syncing team channels.')

        for channel in self.extra_channels:
            _log.debug('Syncing extra channel %s for team %s', channel.id, self)
            await channel._edit({"sync_permissions": True}, reason="Syncing team channels.")  # skipcq: PYL-W0212

    async def add_team_member(self, member_id: int, is_sub: bool = False) -> TeamMember:
        """|coro|

        Add a member to this team.

        Parameters
        -----------
        member_id: :class:`int`
            The id of the member you want to add.
        is_sub: :class:`bool`
            Denotes whether the new member is a sub or not. This defaults
            to ``False`..

        Returns
        -------
        :class:`TeamMember`
            The newly added member.
        """
        async with self.bot.safe_connection() as connection:
            member_record = await connection.fetchrow(
                "INSERT INTO teams.members(team_id, member_id, is_sub) VALUES($1, $2, $3) RETURNING *",
                self.id,
                member_id,
                is_sub,
            )

            if not member_record:
                raise Exception("Failed to add a new member to the team.")

        team_member = TeamMember(self.bot, guild_id=self.guild_id, **dict(member_record))
        self.team_members[team_member.member_id] = team_member

        # Now we can sync the permissions for this member
        await self.sync()
        return team_member

    async def remove_team_member(self, team_member: TeamMember, /, force_voice_disconnect: bool = False) -> None:
        """|coro|

        A method used to remove this member from its team.

        Parameters
        ----------
        team_member: :class:`TeamMember`
            The member you want to remove from the team.
        """
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                "DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2",
                self.id,
                team_member.member_id,
            )

        # Remove this member and sync the channels
        self.team_members.pop(team_member.member_id, None)

        discord_member = await team_member.getch_discord_member()
        if discord_member and discord_member.voice and force_voice_disconnect:
            channel = discord_member.voice.channel
            if channel and channel in (self.voice_channel, *self.extra_channels):
                await discord_member.move_to(None, reason="Member removed from the team.")

        await self.sync()

    async def add_extra_channel(self, channel_id: int, /) -> None:
        await self.edit(extra_channel_ids=self.extra_channel_ids + [channel_id])
        await self.sync()

    async def remove_extra_channel(self, channel_id: int, /) -> None:
        await self.edit(extra_channel_ids=[c_id for c_id in self.extra_channel_ids if c_id != channel_id])
        await self.sync()

    async def edit(
        self,
        /,
        *,
        name: str = MISSING,
        nickname: Optional[str] = MISSING,
        description: Optional[str] = MISSING,
        logo: Optional[str] = MISSING,
        category_channel_id: int = MISSING,
        text_channel_id: int = MISSING,
        voice_channel_id: int = MISSING,
        extra_channel_ids: List[int] = MISSING,
    ) -> None:
        """|coro|

        Edit the team settings and update the team's values, such as name, description, logo, etc.

        Any of these parameters can be omitted to not edit them. Any passed parameters will override
        the current values.

        Parameters
        ----------
        name: :class:`str`
            The new name of the team.
        description: :class:`str`
            The new description of the team.
        logo: :class:`str`
            The new logo of the team.
        category_channel_id: :class:`int`
            Change the teams category channel id.
        text_channel_id: :class:`int`
            Change the teams text channel id.
        voice_channel_id: :class:`int`
            Change the teams voice channel id.
        extra_channel_ids: List[:class:`int`]
            Change the teams extra channel ids.

        Returns
        --------
        None
            When updated, the current instance is edited.
        """
        builder = QueryBuilder("teams.settings")
        builder.add_condition("id", self.id)

        if name is not MISSING:
            builder.add_arg("name", name)
            self.name = name
        if nickname is not MISSING:
            builder.add_arg("nickname", nickname)
            self.nickname = nickname
        if description is not MISSING:
            builder.add_arg("description", description)
            self.description = description
        if logo is not MISSING:
            builder.add_arg("logo", logo)
            self.logo = logo
        if category_channel_id is not MISSING:
            builder.add_arg("category_channel_id", category_channel_id)
            self.category_channel_id = category_channel_id
        if text_channel_id is not MISSING:
            builder.add_arg("text_channel_id", text_channel_id)
            self.text_channel_id = text_channel_id
        if voice_channel_id is not MISSING:
            builder.add_arg("voice_channel_id", voice_channel_id)
            self.voice_channel_id = voice_channel_id
        if extra_channel_ids is not MISSING:
            builder.add_arg("extra_channel_ids", extra_channel_ids)
            self.extra_channel_ids = extra_channel_ids

        async with self.bot.safe_connection() as connection:
            await builder(connection)

    async def _cleanup_practices_for_delete(self, *, connection: ConnectionType) -> None:
        # Cleans up the practices for this team. IE, if the members are the top
        # practicers then their roles must be removed and whatnot

        # Fetch the top practicer team right now
        data = await connection.fetchrow(
            'SELECT top_team_id, role_id FROM teams.practice_leaderboards WHERE guild_id = $1', self.guild_id
        )
        if not data:
            # Nothing to clean up in particular
            return

        top_practicer_team_id = data['top_team_id']

        if not top_practicer_team_id:
            # Nothing to clean up in particular
            return

        # Check if this team is the top practicer team
        if top_practicer_team_id != self.id:
            # Nothing to clean up
            return

        # Alright, we need to clean up the top practicer team
        # Alter the top_team_id to be None, and remove the roles from the members.
        # We set it to None because the top_team_id will be updated in the next iteration of the leaderboard
        # updater.
        await connection.execute(
            'UPDATE teams.practice_leaderboards SET top_team_id = NULL WHERE guild_id = $1', self.guild_id
        )

        # Remove the roles from the members
        guild = self.guild
        if not guild:
            return

        role = guild.get_role(data['role_id'])
        if not role:
            return

        for team_member in self.members:
            discord_member = await team_member.getch_discord_member()
            if not discord_member:
                continue

            try:
                await discord_member.remove_roles(role, reason="Team deleted, team was top practicer.")
            except discord.Forbidden:
                pass

    async def delete(self, *, connection: ConnectionType, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the team and all of its channels.
        """

        # Clean up the practices for this team, if needed
        await self._cleanup_practices_for_delete(connection=connection)

        # Now we can delete it from the database
        await connection.execute("DELETE FROM teams.settings WHERE id = $1", self.id)

        # Remove this team from the bot's cache
        self.bot.remove_team(self.id, self.guild_id)

        reason = reason or "Team deleted automatically."

        voice_channel = self.voice_channel
        if voice_channel:
            await voice_channel.delete(reason=reason)

        text_channel = self.text_channel
        if text_channel:
            await text_channel.delete(reason=reason)

        category_channel = self.category_channel
        if category_channel:
            await category_channel.delete(reason=reason)

        for channel in self.extra_channels:
            await channel.delete(reason=reason)

    async def delete_all_practice_history(self, *, connection: ConnectionType) -> None:
        """|coro|

        Deletes all practice history for this team.
        """
        # (1) Delete all practice history
        await connection.execute("DELETE FROM teams.practice WHERE team_id = $1", self.id)

        # (2) Clear the bot's cache for this
        self.bot.clear_practices_for(self.id, self.guild_id)
