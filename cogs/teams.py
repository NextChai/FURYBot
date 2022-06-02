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

from collections import deque
from typing import TYPE_CHECKING, Literal, Mapping, TypedDict, List, Tuple, Any, Type, Union, Optional, Dict
from typing_extensions import Self

import discord
from discord.ext import commands

from utils.context import Context
from utils import constants, BaseCog
from utils.time import human_join

if TYPE_CHECKING:
    import datetime
    from asyncpg import Record

    from bot import FuryBot

MISSING = discord.utils.MISSING


class _TeamChannel(TypedDict):
    text: int
    voice: int
    category: int


class Team:
    """Represents a Team within the database.

    Contains all operations to modify and view attributes
    on the team.

    Attributes
    ----------
    id: :class:`int`
        The ID of the team.
    """

    def __init__(self, *, guild: discord.Guild, record: Record) -> None:
        self.id: int = record['id']

        self._guild: discord.Guild = guild
        self._team_name: str = record['team_name']
        self._roster: List[int] = record['roster']
        self._subs: List[int] = record['subs']
        self._captain_role: int = record['captain_role']
        self._channels: _TeamChannel = _TeamChannel(**record['channels'])
        self._created: datetime.datetime = record['created']
        self._last_updated: datetime.datetime = record['last_updated']

    @discord.utils.cached_property
    def guild(self) -> discord.Guild:
        """ ":class:`discord.Guild`: The guild this team belongs to."""
        return self._guild

    @property
    def name(self) -> str:
        """str: The name of the team."""
        return self._team_name

    async def roster(self) -> List[discord.Member]:
        """|coro|

        List[:class:`discord.Member`]:
            The members in the team.
        """
        return [(self.guild.get_member(member_id) or await self.guild.fetch_member(member_id)) for member_id in self._roster]

    async def subs(self) -> List[discord.Member]:
        """|coro|

        List[:class:`discord.Member`]:
            Get all sub players in the team.
        """
        return [(self.guild.get_member(member_id) or await self.guild.fetch_member(member_id)) for member_id in self._subs]

    @property
    def captain_role(self) -> discord.Role:
        """:class:`discord.Role`: The role that is used to represent the team captain."""
        role = discord.utils.get(self.guild.roles, id=self._captain_role)
        if not role:
            raise RuntimeError(f'Role {self._captain_role} not found.')

        return role

    @property
    def text_channel(self) -> discord.TextChannel:
        """:class:`discord.TextChannel`: The text channel used for team communication."""
        channel = discord.utils.get(self.guild.text_channels, id=self._channels['text'])
        if not channel:
            raise RuntimeError(f'Text channel {self._channels["text"]} not found.')

        return channel

    @property
    def voice_channel(self) -> discord.VoiceChannel:
        """:class:`discord.VoiceChannel`: The voice channel used for team communication."""
        channel = discord.utils.get(self.guild.voice_channels, id=self._channels['voice'])
        if not channel:
            raise RuntimeError(f'Voice channel {self._channels["voice"]} not found.')

        return channel

    @property
    def category_channel(self) -> discord.CategoryChannel:
        """:class:`discord.CategoryChannel`: The category channel used for team communication."""
        channel = discord.utils.get(self.guild.categories, id=self._channels['category'])
        if not channel:
            raise RuntimeError(f'Category channel {self._channels["category"]} not found.')

        return channel

    async def overwrites(self) -> Mapping[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:
        """Mapping[Union[:class:`discord.Role`, :class:`discord.Member`], :class:`discord.PermissionOverwrite`]:
        A mapping of members and roles to their respective permission overwrites."""
        overwrites: Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite] = {}
        for member in await self.roster():
            overwrites[member] = discord.PermissionOverwrite(view_channel=True)
        for member in await self.subs():
            overwrites[member] = discord.PermissionOverwrite(view_channel=True)

        overwrites[self.captain_role] = discord.PermissionOverwrite(view_channel=True)
        overwrites[self.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        return overwrites

    async def embed(self) -> discord.Embed:
        """|coro|

        :class:`discord.Embed`
            The embed used to represent information about the team.
        """
        bot: FuryBot = self.guild._state._get_client()  # type: ignore

        roster = await self.roster()
        subs = await self.subs()
        captain_role = self.captain_role

        embed = bot.Embed(
            title=f'Team {self.name} Information',
            description=f'{self.name} has {len(roster)} players on the roster and {len(subs)} subs in total.',
        )
        embed.add_field(
            name='Roster', value=human_join([r.mention for r in roster] or ['No roster.'], final='and'), inline=False
        )
        embed.add_field(name='Subs', value=human_join([s.mention for s in subs] or ['No subs.'], final='and'), inline=False)

        embed.add_field(
            name='Team Channels',
            value='\n'.join(
                [
                    f'**Text Channel**: {self.text_channel.mention}',
                    f'**Voice Channel**: {self.voice_channel.mention}',
                    f'**Category**: {self.category_channel.mention}',
                ]
            ),
            inline=False,
        )
        embed.add_field(
            name='Captains',
            value='The captains for this team are {0}. They all have the {1} role.'.format(
                human_join([c.mention for c in captain_role.members], final='and'), captain_role.mention
            ),
            inline=False,
        )

        return embed

    async def edit(
        self,
        *,
        roster: List[discord.Member] = MISSING,
        subs: List[discord.Member] = MISSING,
        captain_role: discord.Role = MISSING,
        text_channel: discord.TextChannel = MISSING,
        voice_channel: discord.VoiceChannel = MISSING,
        category_channel: discord.CategoryChannel = MISSING,
    ) -> None:
        """|coro|

        Edit attributes of the team. This will handle all API calls for you to keep internal cache
        and Discord cache in sync, such as editing channels for you.

        Parameters
        ----------
        roster: List[:class:`discord.Member`]
            A new roster for the team. Please note this overrides the current roster.
        subs: List[:class:`discord.Member`]
            A new list of sub players for the team. Please note this overrides the current subs.
        captain_role: :class:`discord.Role`
            A new role to represent the team captain.
        category_channel: :class:`discord.CategoryChannel`
            A new category channel to use for team communication. This will move the current text and voice
            chats to the new category channel.
        text_channel: :class:`discord.TextChannel`
            A new text channel to use for team communication. This will move the current text chat to the new
            text channel.
        voice_channel: :class:`discord.VoiceChannel`
            A new voice channel to use for team communication. This will move the current voice chat to the new

        Returns
        -------
        None
        """
        query: List[Tuple[str, Any]] = []
        special_query: Dict[Literal['category', 'text', 'voice'], Optional[int]] = {
            'category': None,
            'text': None,
            'voice': None,
        }

        # Category c first
        if category_channel is not MISSING:
            if voice_channel is MISSING:  # Only move them if we dont have a new voice channel
                await self.voice_channel.edit(category=category_channel)
            if text_channel is MISSING:  # Only move them if we dont have a new voice channel
                await self.text_channel.edit(category=category_channel)

            self._channels['category'] = category_channel.id

            special_query['category'] = category_channel.id

        if text_channel is not MISSING:
            # Delete before overwriting
            await self.text_channel.delete()
            await text_channel.edit(category=self.category_channel)

            self._channels['text'] = text_channel.id
            special_query['text'] = text_channel.id

        if voice_channel is not MISSING:
            # Delete before overwriting
            await self.voice_channel.delete()
            await voice_channel.edit(category=self.category_channel)

            self._channels['voice'] = voice_channel.id
            special_query['voice'] = voice_channel.id

        if roster is not MISSING:
            self._roster = [member.id for member in roster]
            query.append(('roster', [r.id for r in roster]))

        if subs is not MISSING:
            self._subs = [member.id for member in subs]
            query.append(('subs', [s.id for s in subs]))

        if captain_role is not MISSING:
            self._captain_role = captain_role.id
            query.append(('captain_role', captain_role.id))

        if not query and not special_query:
            raise ValueError('No changes were made.')

        overwrites = await self.overwrites()
        await self.category_channel.edit(overwrites=overwrites)
        await self.text_channel.edit(sync_permissions=True)
        await self.voice_channel.edit(sync_permissions=True)

        query_maker: List[str] = []
        args: List[Union[str, int, datetime.datetime, Dict[Any, Any]]] = []
        for key, value in query:
            query_maker.append(f'{key}')
            args.append(value)

        if any(v for v in special_query.values()):
            for k, v in special_query.items():
                if not v:
                    special_query[k] = getattr(self, f'{k}_channel')().id

            query_maker.append('channels')
            args.append(special_query)

        query_maker.append('last_updated')
        args.append(discord.utils.utcnow().replace(tzinfo=None))
        args.append(self.id)

        for index, entry in enumerate(query_maker):
            query_maker[index] = entry + f' = ${index+1}'

        sql_query = 'update teams set ' + ', '.join(query_maker) + ' where id = $' + str(len(query_maker) + 1)

        client: FuryBot = self.guild._state._get_client()  # type: ignore
        async with client.safe_connection() as conn:
            await conn.execute(sql_query, *args)


if TYPE_CHECKING:
    TeamConverter = Team
else:

    class TeamConverter(commands.IDConverter[Team]):
        """Converts a team from a given argument to a :class:`Team` object.

        Attributes
        ----------
        multiple: :class:`bool`
            Whether or not to convert as many teams as possible, or just one.
        """

        multiple: bool = False

        def __init__(self, *, multiple: bool = False) -> None:
            self.multiple: bool = multiple

        async def convert(self, ctx: Context, argument: str) -> Union[Team, List[Team]]:
            """|coro|

            Does the actual team conversion from a given argument.

            Parameters
            ----------
            ctx: :class:`Context`
                The context of the command.
            argument: :class:`str`
                The argument to convert.

            Returns
            -------
            :class:`Team`

            Raises
            ------
            commands.NoPrivateMessage
                The command was used in a private message.
            commands.BadArgument
                The argument could not be converted to a valid team.
            """
            bot = ctx.bot
            guild = ctx.guild
            if guild is None:
                raise commands.NoPrivateMessage('This command can not be used in private messages.')

            query = """
                SELECT * FROM teams

                WHERE (channels::jsonb->'text')::bigint = $1
                OR (channels::jsonb->'voice')::bigint = $1
                OR (channels::jsonb->'category')::bigint = $1

                -- Team ID --
                OR id = $1
            """

            async with bot.safe_connection() as connection:

                # Let's see if we can save some time
                match = self._get_id_match(argument)
                if argument.isdigit() or match:
                    if match:
                        argument = match.groups()[0]

                    # Let's see if we can save some time
                    record = await connection.fetch(query, int(argument))
                    if record:
                        return (
                            Team(record=record[0], guild=guild)
                            if not self.multiple
                            else [Team(record=r, guild=guild) for r in record]
                        )

                converters: Tuple[Type[commands.Converter], ...] = (
                    commands.MemberConverter,
                    commands.RoleConverter,
                    commands.TextChannelConverter,
                    commands.VoiceChannelConverter,
                    commands.CategoryChannelConverter,
                )

                for converter in converters:
                    try:
                        converted = await converter().convert(ctx, argument)
                        break
                    except commands.BadArgument:
                        pass
                else:
                    # Break did not get called, let's check for team name
                    record = await connection.fetch('SELECT * FROM teams WHERE LOWER(team_name) = $1', str(argument).lower())
                    if record:
                        return (
                            Team(record=record[0], guild=guild)
                            if not self.multiple
                            else [Team(record=r, guild=guild) for r in record]
                        )

                    raise commands.BadArgument('I could not find the team you requested.')

                record = await connection.fetch(query, converted.id)
                if not record:
                    raise commands.BadArgument('I could not find the team you requested.')

                return (
                    Team(record=record[0], guild=guild)
                    if not self.multiple
                    else [Team(record=r, guild=guild) for r in record]
                )


class TeamSelect(discord.ui.Select['SelectATeam']):
    """A select menu used to allow a user to select a specific team. This is
    so if there's a team name conflict, it can be sorted easily.

    Attributes
    ----------
    parent: :class:`TeamSelector`
        The parent of this select.
    """

    def __init__(self, parent: SelectATeam, teams: List[Team]) -> None:
        super().__init__(
            placeholder='Select a team...',
            options=[discord.SelectOption(label=team.name, value=str(team.id)) for team in teams],
        )
        self.parent: SelectATeam = parent

    async def callback(self, interaction: discord.Interaction) -> Any:
        """|coro|

        The main callback that gets called when the select has been
        interacted with.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the user interacting with this
            select.

        """
        self.parent.selected = self.values[0]
        await interaction.response.send_message(f'Selected team: {self.values[0]}', ephemeral=True)
        self.parent.stop()


class SelectATeam(discord.ui.View):
    """A middle class used to implemet the select
    menu for selecting a team.

    Attributes
    ----------
    selected: Optional[:class:`str`]
        The selected string representation of the team that was selected,
        if any.
    """

    def __init__(self, teams: List[Team]) -> None:
        super().__init__()
        self.selected: Optional[str] = None
        self.add_item(TeamSelect(self, teams))


class TeamPaginator(discord.ui.View):
    """A paginator used to display every team that has been registered.

    Parameters
    ----------
    embeds: List[:class:`discord.Embed`]
        A list of embeds representing the teams to display.
    """

    def __init__(self, embeds: List[discord.Embed]) -> None:
        self._embeds = embeds
        self._queue = deque(embeds)
        self._initial = embeds[0]
        self._len = len(embeds)

        super().__init__(timeout=90)

    @discord.ui.button(emoji='\N{LEFTWARDS BLACK ARROW}')
    async def previous_embed(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """|coro|

        Called to go back a page.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the user interacting with the button.
        button: :class:`discord.ui.Button`
            The button that was pressed on the view.
        """
        self._queue.rotate(-1)
        embed = self._queue[0]
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(emoji='\N{BLACK RIGHTWARDS ARROW}')
    async def next_embed(self, interaction: discord.Interaction, button: discord.ui.Button[Self]):
        """|coro|

        Called to go forward a page.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the user interacting with the button.
        button: :class:`discord.ui.Button`
            The button that was pressed on the view.
        """
        self._queue.rotate(1)
        embed = self._queue[0]
        await interaction.response.edit_message(embed=embed)

    @discord.utils.cached_property
    def initial(self) -> discord.Embed:
        """:class:`discord.Embed`: The initial embed to display."""
        return self._initial


class Teams(BaseCog, brief='A cog to manage teams.', emoji='\N{STEAM LOCOMOTIVE}'):
    """
    A cog to manage, create, and view teams within the FLVS Fury Discord server.
    """

    async def cog_check(self, ctx: Context) -> bool:  # type: ignore
        """|coro|

        A check called before each command invoke to ensure the user
        is authorized to invoke the command. The user is authorized
        if they are a captain, coach, mod, or have the bypass furybot role.

        Parameters
        ----------
        ctx: :class:`Context`
            The context of the command.

        Returns
        -------
        :class:`bool`
            Whether or not the user is authorized to invoke the command.
        """
        if isinstance(ctx.author, discord.User):
            return False
        if not ctx.guild:
            return False

        authorized = (constants.CAPTAIN_ROLE, constants.MOD_ROLE, constants.COACH_ROLE, constants.BYPASS_FURY)
        return any(r.id in authorized for r in ctx.author.roles)

    @commands.group(name='teams', description='View all current teams.')
    async def teams(self, ctx: Context) -> Optional[discord.Message]:
        """|coro|

        View all of the current teams registered to the server.
        """

        guild = ctx.guild
        if not guild:
            raise commands.NoPrivateMessage('This command can only be used in a server.')

        async with self.bot.safe_connection() as conn:
            data = await conn.fetch('SELECT * FROM teams')

        embeds = [await team.embed() for team in (Team(guild=guild, record=record) for record in data)]
        if not embeds:
            return await ctx.send('There are no teams registered to this server.')

        view = TeamPaginator(embeds=embeds)
        await ctx.send(embed=view.initial, view=view)

    @commands.group(name='team', description='View and create teams.', invoke_without_command=True)
    async def team(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        View a specific FLVS Fury team. If no team is specified, the current channel that the command
        is being invoked in will be used to find the team. If you want to specify a specific team, you
        can use a member in the team, the team's channel ids, mentioning a team's channel, mentioning
        a sub on the team, or the team's captain role.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get information about. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if ctx.invoked_subcommand:
            return

        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        embed = await team.embed()
        return await ctx.send(embed=embed)

    @team.command(name='register', description='Register a new team from an existing one', hidden=True)
    @commands.guild_only()
    async def team_register(
        self,
        ctx: Context,
        name: str,
        roster: List[discord.Member] = commands.parameter(converter=commands.Greedy[discord.Member]),
        captain_role: discord.Role = Any,
        text_channel: discord.TextChannel = Any,
        voice_channel: discord.VoiceChannel = Any,
        category: discord.CategoryChannel = Any,
    ) -> Optional[discord.Message]:
        """|coro|

        A private helper command to register a team that is not registered.

        Parmaters
        ---------
        name: :class:`str`
            The name of the team.
        roster: :class:`List[:class:`discord.Member`]`
            The members on the team.
        captain_role: :class:`discord.Role`
            The captain role of the team.
        text_channel: :class:`discord.TextChannel`
            The text channel of the team.
        voice_channel: :class:`discord.VoiceChannel`
            The voice channel of the team.
        category: :class:`discord.CategoryChannel`
            The category channel of the team.
        """
        assert ctx.guild is not None

        # Clean the roster for dups
        roster = list(set(roster))

        @commands.command()
        async def _dummy_g_p(ctx: Any, param: commands.Greedy[discord.Member]):  #  _dummy_g_p -> dummy greedy positional
            return

        subs: List[discord.Member] = []
        sub_obj = await ctx.prompt('Does this team have any subs?')
        if sub_obj:
            new_ctx = await self.bot.get_context(message=sub_obj, cls=type(ctx))
            subs = await _dummy_g_p.transform(new_ctx, _dummy_g_p.clean_params['param'], commands.core._AttachmentIterator(data=[]))  # type: ignore
            subs = list(set(subs))  # Clean dups

        embed = self.bot.Embed(
            title='To confirm..',
            description='Please confirm this is all correct.',
        )
        embed.add_field(name='Team Name', value=name, inline=False)
        embed.add_field(name='Roster', value=human_join([m.mention for m in roster], final='and') or 'None', inline=False)
        embed.add_field(name='Subs', value=human_join([m.mention for m in subs], final='and') or 'None', inline=False)
        embed.add_field(name='Captain Role', value=captain_role.mention)
        embed.add_field(
            name='Team Channels',
            value='\n'.join(
                [
                    f'**Text Channel**: {text_channel.mention}',
                    f'**Voice Channel**: {voice_channel.mention}',
                    f'**Category**: {category.mention}',
                ]
            ),
            inline=False,
        )

        confirmation = await ctx.get_confirmation(embed=embed)
        if not confirmation:
            return

        query = 'INSERT INTO teams (team_name, roster, subs, captain_role, channels) VALUES ($1, $2, $3, $4, $5) RETURNING *'
        async with self.bot.safe_connection() as connection:
            record = await connection.fetchrow(
                query,
                name,
                [r.id for r in roster],
                [s.id for s in subs],
                captain_role.id,
                {'text': text_channel.id, 'voice': voice_channel.id, 'category': category.id},
            )

        team = Team(guild=ctx.guild, record=record)
        return await ctx.send(embed=await team.embed())

    @team.command(name='view', description='View a team and get some information on it.', aliases=['info'])
    async def team_view(self, ctx: Context, *, team: Optional[TeamConverter]) -> None:
        """|coro|

        View some information about a specific team.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get information about. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        await self.team(ctx, team=team)

    @team.command(name='create', description='Create a team and get some information about it.')
    async def team_create(self, ctx: Context) -> Optional[discord.Message]:
        """|coro|

        Create a team!
        """
        # Let's make this user friendly... I mean, not everyone that makes the bot is going to use it.
        guild = ctx.guild
        if guild is None:
            raise commands.NoPrivateMessage('This command cannot be used in a private message.')

        # Get team name
        team_name_obj = await ctx.prompt(
            'What is the name of the team you want to create? For example: `Rocket League 1`, `Valorant 2`, etc.'
        )
        if not team_name_obj:
            return
        team_name = team_name_obj.content

        # Let's do a quick check to make sure a team like this doesn't already exist
        check = await self.bot.pool.fetchval('SELECT EXISTS(SELECT 1 FROM teams WHERE team_name=$1)', team_name)
        if check:
            return await ctx.send('A team with this name already exists! Delete it before creating a new one.')

        # Now let's get the members in the team.
        member_list_obj = await ctx.prompt(
            'Nice! What members do you want to add to the team? You can add multiple members at once by mentioning them.'
        )
        if not member_list_obj:
            return

        # In order to get commands.Greedy to transform,
        # we need a dummy command to work on, this is that command.
        @commands.command()
        async def _dummy_g_p(ctx: Any, param: commands.Greedy[discord.Member]):  #  _dummy_g_p -> dummy greedy positional
            return

        new_ctx = await self.bot.get_context(message=member_list_obj, cls=type(ctx))
        roster = await _dummy_g_p.transform(new_ctx, _dummy_g_p.clean_params['param'], commands.core._AttachmentIterator(data=[]))  # type: ignore

        try:
            sub_obj = await ctx.prompt(
                'Fantastic! What subs do you want to add to the team? Say `none` if you don\'t want to add any subs.'
            )
        except ValueError:
            subs = []
        else:
            if not sub_obj:
                return

            new_ctx = await self.bot.get_context(message=sub_obj, cls=type(ctx))
            subs: List[discord.Member] = await _dummy_g_p.transform(new_ctx, _dummy_g_p.clean_params['param'], commands.core._AttachmentIterator(data=[]))  # type: ignore

        captain_role_obj = await ctx.prompt('Great! Please enter the name or mention the captain role for this team.')
        if not captain_role_obj:
            return

        captain_role = await commands.RoleConverter().convert(ctx, captain_role_obj.content)

        await ctx.typing()

        # Let's create the team now
        team_tc_fmt = team_name.replace(' ', '-').lower()  # text channel
        team_vc_fmt = f'{team_name} Voice'  # voice channel
        team_c_fmt = team_name  # category

        member_overwrites = {m: discord.PermissionOverwrite(view_channel=True) for m in roster + subs}
        role_overwrites = {
            captain_role: discord.PermissionOverwrite(view_channel=True),
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        category_channel = await guild.create_category(
            team_c_fmt, overwrites={**member_overwrites, **role_overwrites}, reason='New Team Category'
        )
        text_channel = await category_channel.create_text_channel(team_tc_fmt, reason='New Team Text Channel')
        voice_channel = await category_channel.create_voice_channel(team_vc_fmt, reason='New Team Voice Channel')

        query = 'INSERT INTO teams (team_name, roster, subs, captain_role, channels) VALUES ($1, $2, $3, $4, $5) RETURNING *'
        async with self.bot.safe_connection() as conn:
            record = await conn.fetchrow(
                query,
                team_name,
                [m.id for m in roster],
                [sub.id for sub in subs],
                captain_role.id,
                {'text': text_channel.id, 'voice': voice_channel.id, 'category': category_channel.id},
            )

        team = Team(guild=guild, record=record)
        embed = await team.embed()
        embed.title = f'Team {team.name} has been craeted!'
        return await ctx.send(embed=embed)

    @team.command(name='delete', aliases=['remove', 'del', 'rm'], description='Delete a team.')
    async def team_delete(self, ctx: Context, *, team: TeamConverter = None) -> Optional[discord.Message]:  # type: ignore
        """|coro|

        Delete a team and all of its channels.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get information about. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        result = await ctx.get_confirmation('Are you sure you want to delete this team? This action can not be undone.')
        if not result:
            return

        await ctx.typing()

        for channel in (team.text_channel, team.voice_channel, team.category_channel):
            await channel.delete(reason='Team deleted')

        async with self.bot.safe_connection() as conn:
            await conn.execute('DELETE FROM teams WHERE id = $1', team.id)

    @team.command(name='sync', description='Channel permissions got messed up? Sync them using this command.')
    async def team_sync(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        A command used to sync the permissions of the team's channels. This is best to be used
        when something goofed with the channel's permissions.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to sync channels on. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        category = team.category_channel
        await category.edit(overwrites=await team.overwrites())
        await team.text_channel.edit(category=category, sync_permissions=True)
        await team.voice_channel.edit(category=category, sync_permissions=True)

        return await ctx.send('Permissions were synced successfully.')

    @commands.group(name='roster', description='Manage and add members to a team\'s roster', invoke_without_command=True)
    async def roster(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        View the current roster of a team.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get roster information on. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if ctx.invoked_subcommand:
            return

        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        roster = await team.roster()
        embed = self.bot.Embed(title=f'{team.name} has {len(roster)} members on the roster total.')
        if roster:
            embed.description = human_join([f'{member.mention}' for member in roster], final='and')

        return await ctx.send(embed=embed)

    @roster.command(name='demote', description='Switch a member from roster to sub.', aliases=['sub', 'substitute'])
    async def roster_demote(self, ctx: Context, member: discord.Member) -> Optional[discord.Message]:
        try:
            team: Team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
        except:
            return await ctx.send('This command was not used in a team\'s channel.')

        roster = await team.roster()
        if member not in roster:
            return await ctx.send('That member is not on the roster.')

        subs = await team.subs()

        roster.remove(member)
        subs.append(member)
        await team.edit(roster=roster, subs=subs)
        return await ctx.send(f'{member.mention} has been demoted to a sub.')

    @roster.command(
        name='switch',
        description='Switch a roster member from one team to another.',
        aliases=[
            'move',
        ],
    )
    async def roster_switch(
        self, ctx: Context, member: discord.Member, *, new_team: TeamConverter
    ) -> Optional[discord.Message]:
        """|coro|

        Switch a roster member from one team to another.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to switch to the other team.
        new_team: Optional[:class:`TeamConverter`]
            The team the member should be switched to.
        """
        try:
            team: Team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
        except:
            return await ctx.send('This command was not used in a team\'s channel.')

        roster = await team.roster()
        if member not in roster:
            return await ctx.send(f'{member.mention} is not on the `{team.name}` roster.')

        roster.remove(member)

        new_roster = await new_team.roster()
        new_roster.append(member)

        await team.edit(roster=roster)
        await new_team.edit(roster=new_roster)
        return await ctx.send(f'I have moved {member.mention} from `{team.name}` to `{new_team.name}`.')

    @roster.command(name='sync', description='Sync the team\'s roster with the server.')
    async def roster_sync(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        Sync the team's roster with the server.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get roster information on. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        await self.team_sync(ctx, team=team)

    @roster.command(name='add', description='Add a member to a team\'s roster.')
    async def roster_add(
        self, ctx: Context, member: discord.Member, *, team: Optional[TeamConverter]
    ) -> Optional[discord.Message]:
        """|coro|

        Add a member to the roster of a team.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to add to the team.
        team: Optional[:class:`TeamConverter`]
            The team to add a member to. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        roster = await team.roster()
        if member in roster:
            return await ctx.send(f'{member.mention} is already on the roster for team {team.name}.')

        roster.append(member)
        await team.edit(roster=roster)
        return await ctx.send(f'{member.mention} has been added to {team.name}.')

    @roster.command(name='remove', description='Remove a member from a team\'s roster.')
    async def roster_remove(
        self, ctx: Context, member: discord.Member, *, team: Optional[TeamConverter]
    ) -> Optional[discord.Message]:
        """|coro|

        Remove a member from the roster of a team.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to add to the team.
        team: Optional[:class:`TeamConverter`]
            The team to remove a roster from. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        roster = await team.roster()
        if member not in roster:
            return await ctx.send(f'{member.mention} is not on the roster for team {team.name}')

        roster.remove(member)
        await team.edit(roster=roster)
        return await ctx.send(f'{member.mention} has been removed from team {team.name}.')

    @commands.group(
        name='sub', description='Manage and add subs to the team.', aliases=['subs'], invoke_without_command=True
    )
    async def sub(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        View the current subs on a team.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to view subs for. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if ctx.invoked_subcommand:
            return

        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        subs = await team.subs()
        embed = self.bot.Embed(title=f'{team.name} has {len(subs)} subs total.')
        if subs:
            embed.description = human_join([f'{sub.mention}' for sub in subs], final='and')

        return await ctx.send(embed=embed)

    @sub.command(name='promote', description='Switch a member from sub to the roster.', aliases=['roster'])
    async def sub_promote(self, ctx: Context, member: discord.Member) -> Optional[discord.Message]:
        try:
            team: Team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
        except:
            return await ctx.send('This command was not used in a team\'s channel.')

        subs = await team.subs()
        if member not in subs:
            return await ctx.send('That member is not on the subs.')

        roster = await team.roster()

        subs.remove(member)
        roster.append(member)
        await team.edit(roster=roster, subs=subs)
        return await ctx.send(f'{member.mention} has been promoted to the roster.')

    @sub.command(
        name='switch',
        description='Switch a sub member from one team to another.',
        aliases=[
            'move',
        ],
    )
    async def sub_switch(
        self, ctx: Context, member: discord.Member, *, new_team: TeamConverter
    ) -> Optional[discord.Message]:
        """|coro|

        Switch a sub member from one team to another.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to switch to the other team.
        new_team: Optional[:class:`TeamConverter`]
            The team the member should be switched to.
        """
        try:
            team: Team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
        except:
            return await ctx.send('This command was not used in a team\'s channel.')

        subs = await team.subs()
        if member not in subs:
            return await ctx.send(f'{member.mention} is not on the `{team.name}` sub list.')

        subs.remove(member)

        new_subs = await new_team.roster()
        new_subs.append(member)

        await team.edit(subs=subs)
        await new_team.edit(roster=new_subs)
        return await ctx.send(f'I have moved {member.mention} from `{team.name}` to `{new_team.name}`.')

    @sub.command(name='sync', description='Sync the team\'s roster with the server.')
    async def sub_sync(self, ctx: Context, *, team: Optional[TeamConverter]) -> Optional[discord.Message]:
        """|coro|

        Sync the team's sub members with the server.

        Parameters
        ----------
        team: Optional[:class:`TeamConverter`]
            The team to get roster information on. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        await self.team_sync(ctx, team=team)

    @sub.command(name='add', description='Add a member to the subs list.')
    async def sub_add(
        self, ctx: Context, member: discord.Member, *, team: Optional[TeamConverter]
    ) -> Optional[discord.Message]:
        """|coro|

        Used to add a member to the subs list of a team.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to add to the subs list.
        team: Optional[:class:`TeamConverter`]
            The team to add a member to. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        subs = await team.subs()
        if member in subs:
            return await ctx.send(f'{member.mention} is already a sub.')

        subs.append(member)
        await team.edit(subs=subs)
        return await ctx.send(f'I have added {member.mention} to the subs list.')

    @sub.command(name='remove', description='Remove a member from the subs list.')
    async def sub_remove(
        self, ctx: Context, member: discord.Member, *, team: Optional[TeamConverter]
    ) -> Optional[discord.Message]:
        """|coro|

        Used to remove a member from the subs list of a team.

        Parameters
        ----------
        member: :class:`discord.Member`
            The member to remove from the subs list.
        team: Optional[:class:`TeamConverter`]
            The team to remove a member from. If none is provided, the team
            will be found from the channel the command is invoked in.
        """
        if not team:
            team = await TeamConverter().convert(ctx, str(ctx.channel.id))  # type: ignore
            if not team:
                return

        subs = await team.subs()
        if member not in subs:
            return await ctx.send(f'{member.mention} is not a sub.')

        subs.remove(member)
        await team.edit(subs=subs)
        return await ctx.send(f'I have removed {member.mention} from the subs list.')


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
