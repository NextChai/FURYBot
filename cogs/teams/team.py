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
from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type, Union, cast

import discord
from typing_extensions import Self

from utils import MiniQueryBuilder

if TYPE_CHECKING:
    import asyncpg

    from bot import FuryBot

    from .practices import Practice
    from .scrim import Scrim

MISSING = discord.utils.MISSING


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

    bot: FuryBot
    team_id: int
    member_id: int
    guild_id: int
    is_sub: Optional[bool] = dataclasses.field(default=None)

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.member_id == __o.member_id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

    def __hash__(self) -> int:
        return hash(self.member_id)

    @property
    def team(self) -> Team:
        """:class:`Team`: The team that this member is on."""
        team = self.bot.get_team(self.team_id, self.guild_id)
        assert team
        return team

    @property
    def member(self) -> Optional[discord.Member]:
        """Optional[:class:`discord.Member`]: A Discord member object."""
        guild = self.team.guild
        return guild.get_member(self.member_id)

    @property
    def mention(self) -> str:
        """:class:`str`: A mention of the member."""
        return f'<@{self.member_id}>'

    async def remove_from_team(self) -> None:
        return await self.team.remove_team_member(self)

    async def demote(self) -> None:
        """|coro|

        A method used to demote the member from the main roster to a sub on the team.

        Raises
        ------
        Exception
            The member is already a sub.
        """
        if self.is_sub:
            raise Exception('Can not demote a sub.')

        self.is_sub = True

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.members SET is_sub = True WHERE team_id = $1 AND member_id = $2', self.team.id, self.member_id
            )

    async def promote(self) -> None:
        """|coro|

        A method used to promote a member on the team from a sub onto the main roster.

        Raises
        ------
        Exception
            The member is already on the main roster.
        """
        if not self.is_sub:
            raise Exception('Can not promote a player on the main roster.')

        self.is_sub = False

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.members SET is_sub = False WHERE team_id = $1 AND member_id = $2', self.team.id, self.member_id
            )

    async def fetch_member(self) -> discord.Member:
        """|coro|

        A method to fetch the :class:`discord.Member` represented by this
        :class:`TeamMember`.
        """
        guild = self.team.guild
        return await guild.fetch_member(self.member_id)


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
    captain_role_ids: List[:class:`int`]
        A team always has a captain. Any captain role assigned
        to the team will get permissions to view the channels
        and make announcements.
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
    captain_role_ids: List[int]
    extra_channel_ids: List[int]
    team_members: Dict[int, TeamMember]
    nickname: Optional[str]
    description: Optional[str]
    logo: Optional[str]

    def __eq__(self, __o: object) -> bool:
        return isinstance(__o, self.__class__) and self.id == __o.id

    def __ne__(self, __o: object) -> bool:
        return not self.__eq__(__o)

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
        Exception
            A team belonging to the channel was not found.
        """
        teams = bot.get_teams(guild_id)
        if teams is []:
            raise Exception('No team with that channel exists.')

        for team in teams:
            if team.has_channel(channel_id):
                return team

        raise Exception('No team with that channel exists.')

    @classmethod
    async def from_record(
        cls: Type[Self],
        data: Dict[str, Any],
        member_data: List[Dict[str, Any]],
        /,
        *,
        bot: FuryBot,
    ) -> Self:
        """|coro|

        Fetch the team from the database and return its instance. This will only be called in
        :meth:`FurtBot.setup_hook` as all other instances should use the bots cache.

        Parameters
        ----------
        data: :class:`dict`
            The data returned from the database.
        member_data: List[:class:`dict`]
            The data returned from the database.
        bot: :class:`FuryBot`
            The bot instance.
        connection: :class:`asyncpg.Connection`
            The connection to the database.

        Returns
        -------
        :class:`Team`
            The fetched team.
        """
        members = {
            entry['member_id']: TeamMember(bot, guild_id=data['guild_id'], **dict(entry)) for entry in member_data or []
        }
        team = cls(bot, **dict(data), team_members=members)
        bot.add_team(team)

        return team

    @classmethod
    async def create(cls: Type[Self], name: str, /, *, guild: discord.Guild, bot: FuryBot) -> Self:
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
            name=name, overwrites={guild.default_role: discord.PermissionOverwrite(read_messages=False)}
        )
        text_channel = await guild.create_text_channel(name='team-chat', category=category)
        voice_channel = await guild.create_voice_channel(name='Team Voice', category=category)

        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO teams.settings (guild_id, category_channel_id, text_channel_id, voice_channel_id, name) '
                'VALUES($1, $2, $3, $4, $5) RETURNING *',
                guild.id,
                category.id,
                text_channel.id,
                voice_channel.id,
                name,
            )
            assert data

        team = cls(bot, **dict(data), team_members={})
        bot.add_team(team)

        return team

    @property
    def guild(self) -> discord.Guild:
        """:class:`discord.Guild`: The guild this team is bound to."""
        return cast(discord.Guild, self.bot.get_guild(self.guild_id))

    @property
    def members(self) -> List[TeamMember]:
        return list(self.team_members.values())

    @property
    def text_channel(self) -> discord.TextChannel:
        """:class:`discord.TextChannel`: The text channel this team is bound to."""
        guild = self.guild
        return cast(discord.TextChannel, guild.get_channel(self.text_channel_id))

    @property
    def voice_channel(self) -> discord.VoiceChannel:
        """:class:`discord.VoiceChannel`: The voice channel this team is bound to."""
        guild = self.guild
        return cast(discord.VoiceChannel, guild.get_channel(self.voice_channel_id))

    @property
    def category_channel(self) -> discord.CategoryChannel:
        """:class:`discord.CategoryChannel`: The category channel this team is bound to."""
        guild = self.guild
        return cast(discord.CategoryChannel, guild.get_channel(self.category_channel_id))

    @property
    def extra_channels(self) -> List[discord.abc.GuildChannel]:
        guild = self.guild
        return [cast(discord.abc.GuildChannel, guild.get_channel(channel_id)) for channel_id in self.extra_channel_ids]

    @property
    def scrims(self) -> List[Scrim]:
        """List[:class:`Scrim`]: A list of all scrims this team has."""
        return self.bot.get_scrims_for(self.id, self.guild_id)

    @property
    def practices(self) -> List[Practice]:
        return self.bot.get_practices_for(self.id, self.guild_id)

    @property
    def ongoing_practice(self) -> Optional[Practice]:
        return discord.utils.find(lambda practice: practice.ongoing, self.practices)

    @property
    def captain_roles(self) -> List[discord.Role]:
        guild = self.guild
        return [role for role_id in self.captain_role_ids if (role := guild.get_role(role_id))]

    @property
    def display_name(self) -> str:
        return f'{self.name} {f"({self.nickname})" if self.nickname else ""}'.strip()

    def embed(
        self,
        *,
        title: Optional[Any] = None,
        url: Optional[Any] = None,
        description: Optional[Any] = None,
        author: Optional[Union[discord.User, discord.Member]] = None,
    ) -> discord.Embed:
        embed = self.bot.Embed(title=title, description=description, url=url, author=author)

        if author is None:
            embed.set_thumbnail(url=self.logo)
            embed.set_author(name=self.display_name, icon_url=self.logo, url=self.logo)

        embed.set_footer(text=str(self.id))

        return embed

    def has_channel(self, channel_id: int, /) -> bool:
        return channel_id in [self.category_channel_id, self.text_channel_id, self.voice_channel_id] + self.extra_channel_ids

    def get_member(self, member_id: int, /) -> Optional[TeamMember]:
        return self.team_members.get(member_id)

    def get_practice_streak(self) -> int:
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
        total_time = datetime.timedelta()

        for practice in self.practices:
            prac_time = practice.get_total_practice_time()
            if prac_time is not None:
                total_time += prac_time

        return total_time

    def rank_member_practice_times(self) -> List[Tuple[TeamMember, datetime.timedelta]]:
        """"""
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
        """"""
        member_absences: Counter[TeamMember] = Counter()

        for practice in self.practices:

            for member in practice.missing_members:
                member_absences[member] += 1

        return member_absences.most_common()

    async def fetch_practice_rank(self, *, connection: Optional[asyncpg.Connection[asyncpg.Record]] = None) -> int:
        """|coro|

        Fetches the rank of this team in the practice leaderboard.

        Parameters
        ----------
        connection: Optional[:class:`asyncpg.Connection`]
            The connection to the database.

        Returns
        -------
        :class:`int`
            The rank of the team in the practice leaderboard.
        """
        query = """
        WITH team_time AS (
            SELECT team_id, SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))) as total_time
            FROM teams.practice
            GROUP BY team_id
        )
        SELECT team_id, rank() OVER (ORDER BY total_time DESC) as ranking
        FROM team_time
        WHERE team_id = $1;
        """

        awaitable = connection or self.bot.pool
        rank = await awaitable.fetchrow(query, self.id)
        assert rank

        return rank['ranking']

    async def sync(self) -> None:
        """|coro|

        Syncs the team's channels with the data in the team.
        """
        overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False)
        }

        for member in self.team_members.values():
            discord_member = member.member or await member.fetch_member()
            overwrites[discord_member] = discord.PermissionOverwrite(view_channel=True)

        for role in self.captain_roles:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        await self.category_channel.edit(overwrites=overwrites)

        await self.text_channel.edit(sync_permissions=True)
        await self.voice_channel.edit(sync_permissions=True)

        for channel in self.extra_channels:
            await channel._edit({'sync_permissions': True}, reason='Syncing team channels.')

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
                'INSERT INTO teams.members(team_id, member_id, is_sub) VALUES($1, $2, $3) RETURNING *',
                self.id,
                member_id,
                is_sub,
            )

        assert member_record
        team_member = TeamMember(self.bot, guild_id=self.guild_id, **dict(member_record))

        self.team_members[team_member.member_id] = team_member

        # Update the channel now
        category = self.category_channel
        member = team_member.member or await team_member.fetch_member()
        await category.set_permissions(member, view_channel=True)

        await self.text_channel.edit(sync_permissions=True)
        await self.voice_channel.edit(sync_permissions=True)

        return team_member

    async def remove_team_member(self, team_member: TeamMember, /) -> None:
        """|coro|

        A method used to remove this member from its team.
        """
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', self.id, team_member.member_id
            )

        member = team_member.member or await team_member.fetch_member()

        category = self.category_channel
        overwrites = category.overwrites
        overwrites.pop(member, None)
        await category.edit(overwrites=overwrites)

        await self.text_channel.edit(sync_permissions=True)
        await self.voice_channel.edit(sync_permissions=True)

        # Update the object
        self.team_members.pop(team_member.member_id, None)

    async def add_captain(self, role_id: int, /) -> None:
        """|coro|

        Add a captain role to this team.

        Parameters
        -----------
        role_id: :class:`int`
            The id of the role to add.

        Raises
        -------
        Exception
            This role is already a captain.
        """

        if role_id in self.captain_role_ids:
            raise Exception('This role is already a captain.')

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_role_ids = array_append(captain_role_ids, $1) WHERE id = $2',
                role_id,
                self.id,
            )

        self.captain_role_ids.append(role_id)

        # Update the channel as well
        category = self.category_channel
        role = cast(discord.Role, self.guild.get_role(role_id))
        await category.set_permissions(role, view_channel=True)

    async def remove_captain(self, role_id: int, /) -> None:
        """|coro|

        Remove a captain role from this team.

        Parameters
        -----------
        role_id: :class:`int`
            The id of the role to remove.

        Raises
        -------
        Exception
            This role is not a captain.
        """

        if role_id not in self.captain_role_ids:
            raise Exception('This role is not a captain.')

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_role_ids = array_remove(captain_role_ids, $1) WHERE id = $2',
                role_id,
                self.id,
            )

        self.captain_role_ids.remove(role_id)

        # Update the channel as well
        category = self.category_channel
        role = cast(discord.Role, self.guild.get_role(role_id))
        await category.set_permissions(role, view_channel=False)

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
        sub_role_ids: List[int] = MISSING,
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
        builder = MiniQueryBuilder('teams.settings')
        builder.add_condition('id', self.id)

        if name is not MISSING:
            builder.add_arg('name', name)
            self.name = name
        if nickname is not MISSING:
            builder.add_arg('nickname', nickname)
            self.nickname = nickname
        if description is not MISSING:
            builder.add_arg('description', description)
            self.description = description
        if logo is not MISSING:
            builder.add_arg('logo', logo)
            self.logo = logo
        if category_channel_id is not MISSING:
            builder.add_arg('category_channel_id', category_channel_id)
            self.category_channel_id = category_channel_id
        if text_channel_id is not MISSING:
            builder.add_arg('text_channel_id', text_channel_id)
            self.text_channel_id = text_channel_id
        if voice_channel_id is not MISSING:
            builder.add_arg('voice_channel_id', voice_channel_id)
            self.voice_channel_id = voice_channel_id
        if extra_channel_ids is not MISSING:
            builder.add_arg('extra_channel_ids', extra_channel_ids)
            self.extra_channel_ids = extra_channel_ids
        if sub_role_ids is not MISSING:
            builder.add_arg('sub_role_ids', sub_role_ids)
            self.sub_role_ids = sub_role_ids

        await builder(self.bot)

    async def delete(self) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.settings WHERE id = $1', self.id)

        await self.voice_channel.delete()
        await self.text_channel.delete()
        await self.category_channel.delete()

        for channel in self.extra_channels:
            await channel.delete()
