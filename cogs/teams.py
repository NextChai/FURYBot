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

import itertools
import datetime
import enum
import asyncio
import difflib
from typing import TYPE_CHECKING, Dict, Any, Coroutine, List, Optional, TypeAlias, Union
from typing_extensions import Self

import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

from utils import assertion
from utils.bases.cog import BaseCog
from utils.time import TimeTransformer

if TYPE_CHECKING:
    from bot import FuryBot


def _find_team_text_channel(guild: discord.Guild, channels: List[int]) -> discord.TextChannel:
    channel: Optional[discord.TextChannel] = None
    for channel_id in channels:
        raw_channel = guild.get_channel(channel_id)
        if isinstance(raw_channel, discord.TextChannel):
            channel = raw_channel
            break
    else:
        # We couldn't find the team's text channel, panick
        raise Exception('Couldn\'t find the team\'s text channel.')

    return channel


def _build_scrim_scheduled(
    bot: FuryBot,
    opposing: asyncpg.Record,
    when: datetime.datetime,
    votes: Optional[List[int]] = None,
    opposing_votes: Optional[List[int]] = None,
) -> discord.Embed:
    embed = bot.Embed(
        title='Scrim Scheduled',
        description=f'The scrim against {opposing["name"]} has been scheduled to be played {discord.utils.format_dt(when, "R")}',
    )

    if votes is not None:
        embed.add_field(
            name='Confirmed Members',
            value=', '.join([f'<@{m_id}>' for m_id in votes] or ['No team members have voted yet.']),
        )

    if opposing_votes:
        embed.add_field(
            name='Who am I Playing Against?',
            value='You will be playing against: ' + ', '.join(f'<@{m_id}>' for m_id in opposing_votes),
            inline=False,
        )

    embed.add_field(
        name='How Do I Scrim?',
        value='When the scrim starts, the home team will have a special channel automatically created '
        'in which both teams will be able to communicate and create the private game to play in. After 2 '
        'hours, the chat will automatically be deleted for you.',
        inline=False,
    )

    return embed


# Persistent views for team scrim confirmation from both
class ScrimStatus(enum.Enum):
    pending_scrimmer = 'pending_scrimer'
    scheduled = 'scheduled'
    pending_host = 'pending_host'


class ConfirmAnywaysView(discord.ui.View):
    def __init__(self, parent: ScrimConfirmation, voters: List[int], confirmed_voters: List[int]) -> None:
        self.parent: ScrimConfirmation = parent
        self.voters: List[int] = voters
        self.confirmed_voters: List[int] = confirmed_voters
        super().__init__(timeout=None)

    @property
    def embed(self) -> discord.Embed:
        embed = self.parent.bot.Embed(
            title='Force Confirm?',
            description='All currently confirmed members need to press the "Confirm Anyways" button to force '
            'confirm the scrim.',
        )
        embed.add_field(
            name='Members Needed to Vote:',
            value=', '.join(
                [f'<@{m_id}>' for m_id in self.voters if m_id not in self.confirmed_voters] or ['No members needed to vote.']
            ),
        )
        embed.add_field(
            name='Members Voted:',
            value=', '.join([f'<@{m_id}>' for m_id in self.confirmed_voters] or ['No confirmed voters.']),
            inline=False,
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> Optional[bool]:
        if interaction.user.id not in self.voters:
            return await interaction.response.send_message(
                'You are not a member who has confirmed the scrim, you can not vote on this.', ephemeral=True
            )

        if interaction.user.id in self.confirmed_voters:
            return await interaction.response.send_message('You have already voted on this.', ephemeral=True)

        return True

    @discord.ui.button(label='Confirm Anyways', custom_id='confirm-anyways')
    async def confirm_anyways(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        self.confirmed_voters.append(interaction.user.id)

        async with self.parent.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.scrims SET away_confirm_anyways = ARRAY_APPEND(away_confirm_anyways, $1) WHERE id = $2',
                interaction.user.id,
                self.parent.scrim_id,
            )

        await interaction.response.edit_message(embed=self.embed, view=self)

        if len(self.confirmed_voters) == len(self.voters):
            await interaction.delete_original_response()
            await self.parent.finalize_scrim(interaction)


class ConfirmAnywaysButton(discord.ui.Button['ScrimConfirmation']):
    def __init__(self, *, parent: ScrimConfirmation, voters: List[int], team: asyncpg.Record) -> None:
        self.parent: ScrimConfirmation = parent
        self.voters: List[int] = voters
        self.team: asyncpg.Record = team
        super().__init__(label='Vote to Force Confirm Scrim', custom_id='vote-to-force-confirm-scrim')

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.parent._force_confirm_message_id is not None:
            return await interaction.response.send_message('There is already a vote in progress.', ephemeral=True)

        window = self.parent.when - datetime.timedelta(minutes=30)
        if interaction.created_at < window:
            return await interaction.response.send_message(
                'You can\'t vote to force confirm the scrim unless the scrim has less '
                'than or equal to 30 minutes until its start.',
                ephemeral=True,
            )

        minimum_amount = len(self.parent.members) // 2
        if len(self.voters) < minimum_amount:
            return await interaction.response.send_message(
                'You can\'t vote to force start a scrim when not even half of the members '
                f'required have not confirmed. **{minimum_amount - len(self.voters)} more people need to Confirm** to vote a force start.',
                ephemeral=True,
            )

        await interaction.response.defer(thinking=True)

        view = ConfirmAnywaysView(self.parent, self.parent.votes, [])
        message = await interaction.followup.send(view=view, embed=view.embed, wait=True)

        self.parent._force_confirm_message_id = message.id
        self.parent._force_confirm_votes = []

        async with self.parent.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.scrims SET away_confirm_anyways_message_id = $1, away_confirm_anyways = ARRAY_APPEND(away_confirm_anyways, $2) WHERE id = $3',
                message.id,
                interaction.user.id,
                self.parent.scrim_id,
            )


class ScrimConfirmation(discord.ui.View):
    """Represents a Scrim Confirmation View. This view will
    manage the voting process from both teams confirming the scrim.

    bot: :class:`FuryBot`
        The main bot instance.
    type: :class:`ScrimStatus`
        The status of the scrim. If the type is :attr:`ScrimStatus.pending_host`,
        then the :attr:`voter` is the home team and the :attr:`opposing` is the away team.
        If the type is :attr:`ScrimStatus.pending_scrimmer`,
        then the :attr:`voter` is the away team and the :attr:`opposing` is the home team.
    when: :class:`datetime.datetime`
        Then the scrim will happen.
    voter: :class:`asyncpg.Record`
        The team that's voting to scrim. More information in :attr:`type`.
    opposing: :class:`asyncpg.Record`
        Who the voter team will play against. More information in :attr:`type`.
    members: List[:class:`int`]
        A list of member IDS who are on the :attr:`voter` team.
    votes: List[:class:`int`]
        A list of member IDs who have voted to srim.
    """

    _force_confirm_votes: List[int] = []
    _force_confirm_message_id: Optional[int] = None

    if TYPE_CHECKING:
        message: discord.Message
        scrim_id: int

    def __init__(
        self,
        bot: FuryBot,
        type: ScrimStatus,
        per_team: int,
        *,
        when: datetime.datetime,
        voter: asyncpg.Record,
        opposing: asyncpg.Record,
        members: List[int],
        votes: List[int],
        opposing_votes: Optional[List[int]] = None,
    ) -> None:
        self.bot: FuryBot = bot
        self.type: ScrimStatus = type
        self.per_team: int = per_team
        self.when: datetime.datetime = when
        self.voter: asyncpg.Record = voter
        self.opposing: asyncpg.Record = opposing
        self.members: List[int] = members
        self.votes: List[int] = votes
        self.opposing_votes: Optional[List[int]] = opposing_votes

        super().__init__(timeout=None)

        if self.type is ScrimStatus.pending_scrimmer:
            self.add_item(ConfirmAnywaysButton(parent=self, voters=self.votes, team=self.voter))

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'Do You Want to Scrim Team {self.opposing["name"]}?',
            description=f'Use the "Confirm" button below to scrim **{self.opposing["name"]}** {discord.utils.format_dt(self.when, "R")}! '
            f'I need **{self.per_team - len(self.votes)} more votes** to confirm the scrim, as the the "per-team" is set to {self.per_team}.',
            timestamp=self.when,
        )

        embed.add_field(
            name='Confirmed Members',
            value=', '.join([f'<@{m_id}>' for m_id in self.votes] or ['No team members have voted yet.']),
        )

        if self.opposing_votes:
            embed.add_field(
                name='Who am I Playing Against?',
                value='You will be playing against: ' + ', '.join(f'<@{m_id}>' for m_id in self.opposing_votes),
                inline=False,
            )

        if self.type is ScrimStatus.pending_scrimmer:
            embed.add_field(
                name='Teammates not Showing Up?',
                value='You can force Confirm the scrm and try to play with a less amount of teammates. This requires '
                'confirmation from all confirmed teammates.',
                inline=False,
            )

        embed.set_footer(
            text='You have up until the scrim date to confirm. This message will auto edit itself.',
        )

        return embed

    async def _load_attributes(self, scrim_id: int) -> None:
        await self.bot.wait_until_ready()

        self.scrim_id = scrim_id

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'SELECT guild_id, away_confirm_anyways, away_confirm_anyways_message_id FROM teams.scrims WHERE id = $1',
                scrim_id,
            )
            if not data:
                return

            self._force_confirm_votes = data['away_confirm_anyways']
            self._force_confirm_message_id = data['away_confirm_anyways_message_id']

            if self._force_confirm_message_id:
                view = ConfirmAnywaysView(self, self._force_confirm_votes, [])
                self.bot.add_view(view, message_id=self._force_confirm_message_id)

            guild = self.bot.get_guild(data['guild_id'])
            if not guild:
                return

            team_channel = _find_team_text_channel(guild, self.voter['channels'])

            if self.type is ScrimStatus.pending_host:
                home_message_id = await connection.fetchval(
                    'SELECT home_message_id FROM teams.scrims WHERE id = $1', scrim_id
                )
            else:
                home_message_id = await connection.fetchval(
                    'SELECT away_message_id FROM teams.scrims WHERE id = $1', scrim_id
                )

            message = await team_channel.fetch_message(home_message_id)
            self.message = message

    async def interaction_check(self, interaction: discord.Interaction) -> Optional[bool]:
        if interaction.user.id not in self.members:
            return await interaction.response.send_message('You aren\'t on this team!', ephemeral=True)

        return True

    async def shift_to_opposing_team(self, interaction: discord.Interaction):
        assert interaction.guild

        # Before we do anything else with the other team, let's edit this original message
        embed = self.bot.Embed(
            title='Confirmed!',
            description='I\'m waiting of the opposing team to confirm the scrim. You will receive a message '
            'in this channel when the other team has confirmed, or a message stating the scrim failed to start '
            'if they did not. The other team has until the scrim start date to confirm.',
        )
        await self.message.edit(embed=embed, view=None)

        new_type = ScrimStatus.pending_scrimmer

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'UPDATE teams.scrims SET status = $1 WHERE id = $2 RETURNING away_id',
                new_type.value,
                self.scrim_id,
            )
            assert data is not None

            away_team_id = data['away_id']
            away_team = self.bot.team_cache[away_team_id]

            members = await connection.fetch('SELECT * FROM teams.members WHERE team_id = $1', away_team_id)
            member_ids: List[int] = [m['member_id'] for m in members]

            channel = _find_team_text_channel(interaction.guild, away_team['channels'])

            view = ScrimConfirmation(
                self.bot,
                new_type,
                self.per_team,
                when=self.when,
                voter=away_team,
                opposing=self.voter,
                members=member_ids,
                votes=[],
                opposing_votes=self.votes,
            )
            view.message = await channel.send(embed=view.embed, view=view)
            view.scrim_id = self.scrim_id

            await connection.execute(
                'UPDATE teams.scrims SET away_message_id = $1 WHERE id = $2', view.message.id, self.scrim_id
            )

    async def finalize_scrim(self, interaction: discord.Interaction) -> None:
        assert interaction.guild

        # Let's edit the embed for the current team
        embed = _build_scrim_scheduled(self.bot, self.opposing, self.when, self.votes, self.opposing_votes)
        await self.message.edit(embed=embed, view=None)

        # Now let's fetch the message and edit the embed for the other team
        channel = _find_team_text_channel(interaction.guild, self.opposing['channels'])

        # The "opposing" team in this situation is in reality the home team,
        # due to the type being ScrimStatus.pending_scrimmer
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'UPDATE teams.scrims SET status = $1 WHERE id = $2 RETURNING home_message_id',
                ScrimStatus.scheduled.value,
                self.scrim_id,
            )
            assert data

            message = await channel.fetch_message(data['home_message_id'])
            embed = _build_scrim_scheduled(self.bot, self.voter, self.when, self.opposing_votes, self.votes)
            await message.edit(embed=embed, view=None)

    async def handle_team_full(self, interaction: discord.Interaction) -> None:
        assert interaction.guild

        if self.type is ScrimStatus.pending_host:
            return await self.shift_to_opposing_team(interaction)
        elif self.type is ScrimStatus.pending_scrimmer:
            return await self.finalize_scrim(interaction)

        raise Exception('Unknown type provided.')

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='confirm-scrim')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if interaction.user.id in self.votes:
            return await interaction.response.send_message('You\'ve already voted on this!', ephemeral=True)

        self.votes.append(interaction.user.id)

        async with self.bot.safe_connection() as connection:
            if self.type is ScrimStatus.pending_host:
                await connection.execute(
                    'UPDATE teams.scrims SET home_votes = array_append(home_votes, $1) WHERE id = $2',
                    interaction.user.id,
                    self.scrim_id,
                )

            elif self.type is ScrimStatus.pending_scrimmer:
                await connection.execute(
                    'UPDATE teams.scrims SET away_votes = array_append(away_votes, $1) WHERE id = $2',
                    interaction.user.id,
                    self.scrim_id,
                )

        await interaction.response.edit_message(embed=self.embed, view=self)

        if len(self.votes) == self.per_team:
            await self.handle_team_full(interaction)


class ScrimConverter(app_commands.Transformer):
    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str], /
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        bot: FuryBot = interaction.client  # type: ignore

        async with bot.safe_connection() as connection:
            data = await connection.fetch(
                'SELECT * FROM teams.scrims WHERE creator_id = $1 AND scheduled_for > $2',
                interaction.user.id,
                discord.utils.utcnow(),
            )

        if not data:
            return []

        return [
            app_commands.Choice(
                name=f'{bot.team_cache[entry["away_id"]]["name"]} '
                + entry['scheduled_for'].strftime('%Y-%m-%d %H:%M:%S.%f%z (%Z)'),
                value=str(entry['id']),
            )
            for entry in data
        ]

    async def transform(self, interaction: discord.Interaction, value: Any, /) -> asyncpg.Record:
        if not value.isdigit():
            raise Exception('Invalid team selected.')

        bot: FuryBot = interaction.client  # type: ignore
        async with bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'SELECT * FROM teams.scrims WHERE id = $1 AND creator_id = $2', int(value), interaction.user.id
            )

        if not data:
            raise Exception('Invalid ID given.')

        return data


class TeamTransformer(app_commands.Transformer):
    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str], /
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        # Show available teams
        bot: FuryBot = interaction.client  # type: ignore

        team_mapping = {team['name']: team for team in bot.team_cache.values()}
        if not team_mapping:
            return []

        if not value:
            return [
                app_commands.Choice(name=team['name'], value=str(team['id'])) for team in list(bot.team_cache.values())[:20]
            ]

        similar: List[str] = await bot.wrap(difflib.get_close_matches, str(value), team_mapping.keys(), n=20)  # type: ignore

        first = similar[0]
        first_team = team_mapping[first]
        if first == first_team['name']:
            return [app_commands.Choice(name=first_team['name'], value=str(first_team['id']))]

        return [
            app_commands.Choice(name=team_mapping[entry]['name'], value=str(team_mapping[entry]['id'])) for entry in similar
        ]

    async def transform(self, interaction: discord.Interaction, value: Any, /) -> asyncpg.Record:
        if not value.isdigit():
            raise Exception('Invalid team selected.')

        bot: FuryBot = interaction.client  # type: ignore
        return bot.team_cache[int(value)]


TEAM_TRANSFORM: TypeAlias = app_commands.Transform[asyncpg.Record, TeamTransformer]
SCRIM_TRANSFORM: TypeAlias = app_commands.Transform[asyncpg.Record, ScrimConverter]


class Teams(BaseCog):

    team = app_commands.Group(
        name='team',
        description='Create and manage teams.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )
    team_members = app_commands.Group(name='members', description='Manage team members.', parent=team)
    team_subs = app_commands.Group(name='subs', description='Manage team subs.', parent=team)
    team_captains = app_commands.Group(name='captains', description='Manage team captainis.', parent=team)

    scrim = app_commands.Group(name='scrim', description='Create and manage scrims.', guild_only=True)

    async def _sync_channels(self, guild: discord.Guild, channel_ids: List[int]) -> None:
        for channel_id in channel_ids:
            channel = assertion(guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]])
            if channel:
                await channel.edit(sync_permissions=True)

    def fetch_team(self, category: discord.CategoryChannel) -> Optional[asyncpg.Record]:
        return discord.utils.find(lambda x: x['category_id'] == category.id, self.bot.team_cache.values())

    @scrim.command(name='create', description='Scrim another team!')
    @app_commands.describe(
        per_team='The number of players per team. Max is 10.',
        when='When to scrim (in UTC Time). For example: "Tomorrow at 4pm for practice" is 12pm EST.',
    )
    @app_commands.rename(away_team='team')
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def scrim_create(
        self,
        interaction: discord.Interaction,
        away_team: TEAM_TRANSFORM,
        per_team: app_commands.Range[int, 1, 10],
        when: app_commands.Transform[TimeTransformer, TimeTransformer(default='[NO REASON GIVEN]')],
    ) -> Optional[discord.InteractionMessage]:
        assert when.dt
        assert interaction.guild

        if when.dt - interaction.created_at < datetime.timedelta(minutes=59):
            return await interaction.response.send_message(
                'The minimum amount of time to schedule a scrim is an hour.', ephemeral=True
            )

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                'You need to use this command in a team chat text channel.', ephemeral=True
            )

        category = channel.category
        if not category or not (home_team := self.fetch_team(category)):
            return await interaction.response.send_message(
                'You need to use this command in a team chat text channel.', ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            home_members = await connection.fetch('SELECT member_id FROM teams.members WHERE team_id = $1', home_team['id'])
            home_member_ids = [e['member_id'] for e in home_members]

            if interaction.user.id not in home_member_ids:
                return await interaction.edit_original_response(content='You aren\'t on this team!')

            status = ScrimStatus.pending_host
            view = ScrimConfirmation(
                self.bot,
                status,
                per_team,
                when=when.dt,
                voter=home_team,
                opposing=away_team,
                members=home_member_ids,
                votes=[interaction.user.id],
            )
            channel = _find_team_text_channel(interaction.guild, home_team['channels'])
            await interaction.edit_original_response(content='Scrim Created. You can cancel it using `/scrim cancel`.')

            view.message = await channel.send(embed=view.embed, view=view)

            data = await connection.fetchrow(
                'INSERT INTO teams.scrims (home_id, away_id, home_message_id, status, scheduled_for, guild_id, per_team, home_votes, creator_id) '
                'VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id;',
                home_team['id'],
                away_team['id'],
                view.message.id,
                status.value,
                when.dt,
                interaction.guild.id,
                per_team,
                [interaction.user.id],
                interaction.user.id,
            )
            assert data

            view.scrim_id = data['id']

        await self.bot.timer_manager.create_timer(
            when.dt - datetime.timedelta(minutes=10),
            'scrim_scheduled_start',
            interaction.guild.id,
            data['id'],
        )

    @scrim.command(name='cancel', description='Cancel an existing scrim.')
    @app_commands.describe(scrim='The scrim you want to cancel.')
    async def scrim_cancel(self, interaction: discord.Interaction, scrim: SCRIM_TRANSFORM) -> None:
        assert interaction.guild

        await interaction.response.defer()

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.scrims WHERE id = $1', scrim['id'])

        home_team = self.bot.team_cache[scrim['home_id']]
        away_team = self.bot.team_cache[scrim['away_id']]

        home_channel = _find_team_text_channel(interaction.guild, home_team['channels'])

        embed = self.bot.Embed(
            title='Scrim has been Cancelled.',
            description=f'The creator of the srim, <@{interaction.user.id}> has cancelled the scrim that was '
            f'scheduled for {discord.utils.format_dt(scrim["scheduled_for"], "F")}.',
            author=interaction.user,
        )
        if scrim['home_votes']:
            embed.add_field(
                name='Previously Confirmed Home Team Members',
                value=', '.join([f'<@{m_id}>' for m_id in scrim['home_votes']]),
                inline=False,
            )

        if scrim['away_votes']:
            embed.add_field(
                name='Previously Confirmed Away Team Members',
                value=', '.join([f'<@{m_id}>' for m_id in scrim['away_votes']]),
                inline=False,
            )

        home_message = await home_channel.fetch_message(scrim['home_message_id'])
        await home_message.edit(embed=embed, view=None, content=None)

        if scrim['away_message_id']:
            away_channel = _find_team_text_channel(interaction.guild, away_team['channels'])
            away_message = await away_channel.fetch_message(scrim['away_message_id'])
            await away_message.edit(embed=embed, view=None, content=None)

        if scrim['scrim_chat'] is not None:
            channel = assertion(interaction.guild.get_channel(scrim['scrim_chat']), Optional[discord.TextChannel])
            if channel:
                await channel.send(embed=embed)
                await channel.delete(reason='Scrim Cancelled.')

        await interaction.edit_original_response(content='Scrim has been cancelled.')

    @team.command(name='get', description='Get the team(s) that a specific member is on.')
    async def team_get(self, interaction: discord.Interaction, member: discord.Member) -> None:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM teams.members WHERE member_id = $1', member.id)

        if not data:
            return await interaction.response.send_message(f'{member.mention} is not on any teams.')

        fmt: List[str] = []
        for entry in data:
            team = self.bot.team_cache[entry['team_id']]
            fmt.append(
                f'**{team["name"]}**: {"Is on the main roster." if not entry["is_sub"] else "Is a sub for the team."}'
            )

        return await interaction.response.send_message(f'{member.mention} is on:\n' + '\n'.join(fmt))

    @team.command(name='create', description='Create a team.')
    @app_commands.describe(name='The name of the team.')
    @app_commands.guild_only()
    async def team_create(self, interaction: discord.Interaction, name: str) -> None:
        assert interaction.guild

        if name.lower() in (team['name'].lower() for team in self.bot.team_cache.values()):
            return await interaction.response.send_message(f'Team with the name `{name}` already exists.', ephemeral=True)

        category = await interaction.guild.create_category(
            name=name,
            overwrites={interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)},
            reason='New team.',
        )
        text_channel = await category.create_text_channel(name='team-chat')
        voice_channel = await category.create_voice_channel(name='Team Voice')

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                """
                INSERT INTO teams.settings(category_id, channels, name) VALUES($1, $2, $3)
                RETURNING *
                """,
                category.id,
                [text_channel.id, voice_channel.id],
                name,
            )

            assert data

        self.bot.team_cache[data['id']] = data
        return await interaction.response.send_message(
            f'Team `{name}` has been created. Team general chat {text_channel.mention}.', ephemeral=True
        )

    @team.command(name='delete', description='Delete a team.')
    @app_commands.describe(team='The team to delete.')
    async def team_delete(self, interaction: discord.Interaction, team: Optional[TEAM_TRANSFORM] = None) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.settings WHERE id = $1', team['id'])

        futures: List[Coroutine[Any, Any, Any]] = []
        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                futures.append(channel.delete(reason='Team deleted.'))

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            futures.append(category.delete(reason='Team deleted.'))

        await asyncio.gather(*futures)

        self.bot.team_cache.pop(team['id'], None)
        return await interaction.response.send_message(f'Team {team["name"]} has been deleted.', ephemeral=True)

    @team.command(name='info', description='View stats about a specific team.')
    @app_commands.describe(team='The team to get information on.')
    async def team_info(self, interaction: discord.Interaction, team: Optional[TEAM_TRANSFORM] = None) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            team_roster_data = await connection.fetch('SELECT * FROM teams.members WHERE team_id = $1', team['id'])

        embed = self.bot.Embed(
            title=team['name'], description=f'Below displays some inforamtion about {team["name"]}.', author=interaction.user
        )

        category = interaction.guild.get_channel(team['category_id'])
        embed.add_field(name='Category', value=category and category.name or "Category Deleted.", inline=False)

        channel_fmt: List[str] = []
        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                channel_fmt.append(f'- {channel.mention}')
            else:
                channel_fmt.append(f'- Channel `{channel_id}` deleted.')

        embed.add_field(name='Channels', value='\n'.join(channel_fmt), inline=False)

        members_fmt: List[str] = []
        subs_fmt: List[str] = []
        for entry in team_roster_data:
            mention_fmt = f'<@{entry["member_id"]}>'

            if entry['is_sub']:
                subs_fmt.append(f'- {mention_fmt}')
            else:
                members_fmt.append(f'- {mention_fmt}')

        captains_fmt: List[str] = []
        for entry in team['captain_roles']:
            role = interaction.guild.get_role(entry)
            if role:
                captains_fmt.append(f'- {role.mention}')

        embed.add_field(name='Members', value='\n'.join(members_fmt or ['No members on this team.']), inline=False)
        embed.add_field(name='Subs', value='\n'.join(subs_fmt or ['No subs on this team.']), inline=False)
        embed.add_field(name='Captains', value='\n'.join(captains_fmt or ['No captains on this team.']))
        return await interaction.response.send_message(embed=embed)

    @team_members.command(name='add', description='Add a team member.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the team.')
    async def team_members_add(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> Optional[discord.InteractionMessage]:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if member_data:
                return await interaction.edit_original_response(content='This member is already on the team.')

            await connection.execute('INSERT INTO teams.members(team_id, member_id) VALUES($1, $2)', team['id'], member.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Added {member.mention} to the {team["name"]} team.')

    @team_members.command(name='bulk_add', description='Bulk add members to a team.')
    @app_commands.describe(team="The team to add the member to.")
    async def team_members_bulk_add(
        self,
        interaction: discord.Interaction,
        team: Optional[TEAM_TRANSFORM] = None,
        member1: Optional[discord.Member] = None,
        member2: Optional[discord.Member] = None,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        member6: Optional[discord.Member] = None,
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        members = {
            member.id: member for member in [member1, member2, member3, member4, member5, member6] if member is not None
        }

        async with self.bot.safe_connection() as connection:
            members_data = await connection.fetch(
                "SELECT member_id FROM teams.members WHERE member_id = ANY($1) AND team_id = $2",
                list(members.keys()),
                team['id'],
            )
            for entry in members_data:
                members.pop(entry['member_id'], None)

            await connection.executemany(
                'INSERT INTO teams.members(team_id, member_id) VALUES($1, $2)',
                [(team['id'], member_id) for member_id in members.keys()],
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            for member in members.values():
                await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(
            content='Added {} to the team.'.format(', '.join(m.mention for m in members.values()))
        )

    @team_members.command(name='remove', description='Remove a team member.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_members_remove(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> Optional[discord.InteractionMessage]:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.edit_original_response(content='This member is not on the team.')

            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Removed {member.mention} from the {team["name"]} team.')

    @team_members.command(name='demote', description='Demote a team member to a sub.')
    @app_commands.describe(team='The team to demote the member on.', member='The member to demote.')
    async def team_members_demote(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.response.send_message('This member is not on the team.', ephemeral=True)

            await connection.execute(
                'UPDATE teams.members SET is_sub = True WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Demoted {member.mention} on the {team["name"]} team.', ephemeral=True
        )

    @team_subs.command(name='add', description='Add a member to the subs list.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the subs list.')
    async def team_subs_add(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> Optional[discord.InteractionMessage]:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if member_data:
                return await interaction.edit_original_response(content='This member is already on the team.')

            await connection.execute(
                'INSERT INTO teams.members(team_id, member_id, is_sub) VALUES($1, $2, True)', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Added {member.mention} to {team["name"]}\'s sub roster.')

    @team_subs.command(name='remove', description='Remove a sub from a team.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_subs_remove(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> Optional[discord.InteractionMessage]:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.edit_original_response(content='This member is not on the team.')

            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Removed {member.mention} from {team["name"]}\'s sub roster.')

    @team_subs.command(name='promote', description='Promote a team\'s sub to be apart of the main roster.')
    @app_commands.describe(member='The member to promote.', team='The team to promote the member on.')
    async def team_subs_promote(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.response.send_message('This member is not on the team.', ephemeral=True)

            await connection.execute(
                'UPDATE teams.members SET is_sub = False WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Promoted {member.mention} on the {team["name"]} team.', ephemeral=True
        )

    @team_captains.command(name='add', description='Add a team captain role.')
    @app_commands.describe(role='The role to add.', team='The team to add the captain role to.')
    async def team_captains_add(
        self, interaction: discord.Interaction, role: discord.Role, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        if role.id in team['captain_roles']:
            return await interaction.response.send_message('This role is already a captain.', ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_roles = array_append(captain_roles, $1) WHERE id = $2',
                role.id,
                team['id'],
            )

        team['captain_roles'].append(role.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(role, view_channel=True, reason='Adding new captain.')

        await self._sync_channels(interaction.guild, team['channels'])
        return await interaction.response.send_message(f'Added {role.mention} to the {team["name"]} team.', ephemeral=True)

    @team_captains.command(name='remove', description='Remove a team captain role.')
    @app_commands.describe(role='The role to remove.', team='The team to remove the captain role from.')
    async def team_captains_remove(
        self, interaction: discord.Interaction, role: discord.Role, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        if role.id not in team['captain_roles']:
            return await interaction.response.send_message('This role is not a captain role on this team.', ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_roles = array_remove(captain_roles, $1) WHERE id = $2',
                role.id,
                team['id'],
            )

        team['captain_roles'].remove(role.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(role, None)
            await category.edit(overwrites=overwrites, reason='Removing captain.')

        await self._sync_channels(interaction.guild, team['channels'])
        return await interaction.response.send_message(
            f'Removed {role.mention} from the {team["name"]} team.', ephemeral=True
        )

    @commands.Cog.listener('on_scrim_scheduled_start_timer_complete')
    async def on_scrim_scheduled_start_timer_complete(self, guild_id: int, scrim_id: int) -> Optional[discord.Message]:
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM teams.scrims WHERE id = $1', scrim_id)

            if not data:
                return

            status = ScrimStatus(data['status'])

            home_team = self.bot.team_cache[data['home_id']]
            home_team_channel = _find_team_text_channel(guild, home_team['channels'])

            if status is not ScrimStatus.scheduled:
                # The scrim did not start, we need to edit any messages.
                if status is ScrimStatus.pending_host:
                    embed = self.bot.Embed(
                        title='Scrim has been Cancelled.',
                        description='The required number of members did not confirm the scrim, '
                        'so the scrim was cancelled. If you wish to try again, feel free to schedule '
                        'another scrim.',
                    )

                    message = await home_team_channel.fetch_message(data['home_message_id'])
                    return await message.edit(embed=embed)
                elif status is ScrimStatus.pending_scrimmer:
                    # Edit the host and the scrimmer messages
                    embed = self.bot.Embed(
                        title='Scrim Cancelled',
                        description='The required number of members on the other team did not '
                        'confirm the scrim, so the scrim has been cancelled. If you wish to try again, feel '
                        'free to schedule another scrim.',
                    )

                    message = await home_team_channel.fetch_message(data['home_message_id'])
                    await message.edit(embed=embed)

                    embed = self.bot.Embed(
                        title='Scrim has been Cancelled.',
                        description='The required number of members did not confirm the scrim, '
                        'so the scrim was cancelled. If you wish to try again, feel free to schedule '
                        'another scrim.',
                    )

                    away_team = self.bot.team_cache[data['away_id']]
                    away_team_channel = _find_team_text_channel(guild, away_team['channels'])
                    message = await away_team_channel.fetch_message(data['away_message_id'])
                    return await message.edit(embed=embed)

            overwrites: Dict[Union[discord.Member, discord.Role], discord.PermissionOverwrite] = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False)
            }

            for entry in itertools.chain(*[data['home_votes'], data['away_votes']]):
                member = guild.get_member(entry) or await guild.fetch_member(entry)
                overwrites[member] = discord.PermissionOverwrite(view_channel=True)

            category = assertion(home_team_channel.category, discord.CategoryChannel)
            scrim_channel = await category.create_text_channel(
                name='scrim-chat',
                reason=f'Scrim {scrim_id} starting',
                topic='The scrim text chat to communicate.',
                overwrites=overwrites,
            )

            await connection.execute('UPDATE teams.scrims SET scrim_chat = $1 WHERE id = $2', scrim_channel.id, scrim_id)

        embed = self.bot.Embed(
            title='Scrim Started!',
            description='Welcome to the Scrim Channel! Use this channel to communicate game invite codes, rules, etc.',
            timestamp=data['scheduled_for'],
        )

        embed.add_field(name='Home Team', value=', '.join(f'<@{m_id}>' for m_id in data['home_votes']), inline=False)
        embed.add_field(name='Away Team', value=', '.join(f'<@{m_id}>' for m_id in data['away_votes']), inline=False)

        # NOTE: Add members on each team here

        embed.set_footer(text='Note: This channel will delete itself in 2 hours.')

        await scrim_channel.send(embed=embed, content='@everyone', allowed_mentions=discord.AllowedMentions(everyone=True))

        await self.bot.timer_manager.create_timer(
            discord.utils.utcnow() + datetime.timedelta(hours=2),
            'scrim_channel_timeout',
            guild.id,
            scrim_channel.id,
            scrim_id,
        )

    @commands.Cog.listener('on_scrim_channel_timeout_timer_complete')
    async def on_scrim_channel_timeout_timer_complete(self, guild_id: int, channel_id: int, scrim_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        await channel.delete(reason='Scrim ended.')

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.scrims WHERE id = $1 AND scrim_chat = $2', scrim_id, channel_id)


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
