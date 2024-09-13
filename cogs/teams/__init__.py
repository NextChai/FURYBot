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
from typing import TYPE_CHECKING, Annotated, List, Optional, Tuple, TypeAlias

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, TimeTransformer

from .errors import *
from .practices.panel import TeamPracticesPanel
from .scrims import Scrim
from .scrims.errors import CannotCreateScrim
from .team import Team
from .transformers import TeamTransformer
from .views import TeamView

TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer(clamp_teams=False)]
FRONT_END_TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer(clamp_teams=True)]

if TYPE_CHECKING:
    from bot import FuryBot

    from .team import TeamMember

__all__: Tuple[str, ...] = ('Teams',)

_log = logging.getLogger(__name__)


def _maybe_team(interaction: discord.Interaction[FuryBot], team: Optional[Team]) -> Optional[Team]:
    assert interaction.guild

    if team is not None:
        return team

    channel = interaction.channel
    if not channel:
        return None

    category: Optional[discord.CategoryChannel] = getattr(channel, 'category', None)
    if not category:
        return None

    try:
        return Team.from_channel(category.id, interaction.guild.id, bot=interaction.client)
    except TeamNotFound:
        return None


class Teams(BaseCog):
    """A cog to manage teams and allow teams to create scrims and find subs."""

    team = app_commands.Group(
        name='team',
        description='Create and manage teams.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    scrim = app_commands.Group(name='scrim', description='Create and manage scrims.', guild_only=True)

    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot=bot)

        context_menu = app_commands.ContextMenu(
            name='Team Get',
            callback=self.team_get_context_menu,
            type=discord.AppCommandType.user,
        )
        context_menu.default_permissions = discord.Permissions(moderate_members=True)

        self.bot.tree.add_command(context_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command('Team Get', type=discord.AppCommandType.user)

    @team.command(name='create', description='Create a team.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(name='The name of the team.')
    async def team_create(self, interaction: discord.Interaction[FuryBot], name: str) -> discord.InteractionMessage:
        """|coro|

        Create a team.

        Parameters
        ----------
        name: :class:`str`
            The name of the team.
        """
        assert interaction.guild

        await interaction.response.defer()

        team = await Team.create(name, guild=interaction.guild, bot=self.bot)
        view = TeamView(team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @team.command(name='manage', description='Manage a team. Assign members, subs, captains, scrims, etc.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(team='The team you want to manage.')
    async def team_manage(
        self, interaction: discord.Interaction[FuryBot], team: Optional[TEAM_TRANSFORM]
    ) -> Optional[discord.InteractionMessage]:
        """|coro|

        A command used to manage a team. This will launch an depth view in which you can manage the team.

        Use this command to add subs, remove subs, add members, remove members, create extra channels, assign captain roles,
        etc.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to manage.
        """
        team = _maybe_team(interaction, team)
        if team is None:
            return await interaction.response.send_message(
                'You must be in a team channel to use this command.', ephemeral=True
            )

        await interaction.response.defer()

        view = TeamView(team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @team.command(name='practices', description='Manage a team\'s practices')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(team='The team you want to manage.')
    async def team_practices(
        self, interaction: discord.Interaction[FuryBot], team: Optional[TEAM_TRANSFORM]
    ) -> discord.InteractionMessage:
        await interaction.response.defer(ephemeral=True)

        team = _maybe_team(interaction, team)
        if team is None:
            return await interaction.edit_original_response(content='You must be in a team channel to use this command.')

        view = TeamPracticesPanel(team, target=interaction)
        return await interaction.edit_original_response(view=view, embed=view.embed)

    @team.command(name='delete', description='Delete a team.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(team='The team you want to delete.', reason='Reason for deleting the team, shows on audit logs.')
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    async def team_delete(
        self, interaction: discord.Interaction[FuryBot], team: Optional[TEAM_TRANSFORM], reason: Optional[str] = None
    ) -> Optional[discord.InteractionMessage]:
        """|coro|

        A command used to delete a team.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to delete.
        """
        await interaction.response.defer()

        team = _maybe_team(interaction, team)
        if team is None:
            return await interaction.response.send_message(
                'You must be in a team channel to use this command.', ephemeral=True
            )

        async with self.bot.safe_connection() as connection:
            await team.delete(connection=connection, reason=f'{interaction.user} - {reason or "No reason provided."}')

        return await interaction.edit_original_response(content=f'{team.display_name} has been deleted.')

    @scrim.command(name='create', description='Create a scrim')
    @app_commands.describe(
        team='The team you want to scrim against.',
        when='When you want to scrim the other team. For ex: "Tomorrow at 4pm", "Next tuesday at 12pm", etc.',
        per_team='The amount of players per team. For ex: 5, 3, 2, etc.',
    )
    async def scrim_create(
        self,
        interaction: discord.Interaction[FuryBot],
        team: FRONT_END_TEAM_TRANSFORM,
        when: Annotated[TimeTransformer, TimeTransformer('n/a')],
        per_team: app_commands.Range[int, 2, 10],
    ) -> discord.InteractionMessage:
        """|coro|

        A command used to create a scrim.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to scrim against.
        when: :class:`TimeTransformer`
            When you want to scrim the other team. For ex: "Tomorrow at 4pm", "Next tuesday at 12pm", etc.
        per_team: :class:`int`
            The amount of players per team. For ex: 5, 3, 2, etc.
        """
        assert isinstance(interaction.channel, (discord.abc.GuildChannel, discord.Thread))
        assert interaction.channel.category
        assert interaction.guild
        assert when.dt

        await interaction.response.defer(ephemeral=True)

        try:
            home_team = Team.from_channel(interaction.channel.category.id, interaction.guild.id, bot=self.bot)
        except TeamNotFound:
            return await interaction.edit_original_response(
                content='You must be in a team channel to use this command. Could not find a team from this channel.'
            )

        try:
            scrim = await Scrim.create(
                when.dt, home_team=home_team, away_team=team, per_team=per_team, creator_id=interaction.user.id, bot=self.bot
            )
        except CannotCreateScrim as exc:
            return await interaction.edit_original_response(content=str(exc))

        return await interaction.edit_original_response(
            content=f'A scrim for {scrim.scheduled_for_formatted()} has been created against {team.display_name}.'
        )

    async def _team_get_func(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        team_members: List[TeamMember] = [
            team_member for team in self.bot.get_teams(interaction.guild.id) if (team_member := team.get_member(member.id))
        ]

        if not team_members:
            return await interaction.edit_original_response(content=f'{member.mention} is not on any teams.')

        team_member = team_members[0]
        team = team_member.team

        team_text_chat = team_members[0].team.text_channel

        embed = self.bot.Embed(title=f'{member.display_name} Teams', author=member)
        embed.add_field(
            name=team.display_name,
            value=f'**Team Chat**: {team_text_chat and team_text_chat.mention or "Text chat has been deleted!!"}\n**Is Sub**: {"Is a sub" if team_member.is_sub else "Is not a sub"}',
            inline=False,
        )

        return await interaction.edit_original_response(embed=embed)

    @team.command(name='get', description='Get the team status of a member.')
    async def team_get(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        """|coro|

        Allows you to get the team status of a member.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that triggered this command.
        member: :class:`discord.Member`
            The member you want to get the team status of.
        """
        return await self._team_get_func(interaction, member)

    async def team_get_context_menu(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        """|coro|

        The context command for the team get command. This does not have decorators
        as all management for this command is done in the classes init.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that triggered this command.
        member: :class:`discord.Member`
            The member you want to get the team status of.
        """
        return await self._team_get_func(interaction, member)

    # Automatic listeners for team deletion
    @commands.Cog.listener('on_guild_channel_delete')
    async def team_automatic_deletion_detector(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.CategoryChannel):
            return

        assert channel.guild, 'This should not be possible'

        # This was a category channel, let's check if it was a team
        try:
            team = Team.from_channel(channel.id, channel.guild.id, bot=self.bot)
        except TeamNotFound:
            # A team does not exist with this channel, we can ignore this
            return

        _log.debug('Team %s category channel was deleted, deleting team.', team.display_name)

        # A team does exist with this channel, delete it for the mod
        async with self.bot.safe_connection() as connection:
            await team.delete(
                connection=connection, reason=f'Team {team.display_name} category channel was deleted, team was deleted.'
            )

    @commands.Cog.listener('on_guild_channel_delete')
    async def team_automatic_text_voice_chat_deletion_detector(self, channel: discord.abc.GuildChannel) -> None:
        """|coro|

        Watches to see if a team's main text or voice chat has been deleted. If so, the channel is recreated automatically.
        Having a team main text and voice chat is marked as essential for the team to function, and the default is that
        the channel MUST exist for the team to exist.
        """
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            return

        assert channel.guild, 'This should not be possible'

        # This was a text channel, let's check if it was a team
        try:
            team = Team.from_channel(channel.id, channel.guild.id, bot=self.bot)
        except TeamNotFound:
            # A team does not exist with this channel, we can ignore this
            return

        category = channel.category
        if category is None:
            _log.debug('Team %s category channel was deleted, deleting team.', team.display_name)
            # The category has been deleted, we can assume that the team has been deleted or
            # some other catastrophic event has occurred. We can delete the team, and in the case
            # the team already doesn't exist, this will just be cleaning up the database.
            async with self.bot.safe_connection() as connection:
                return await team.delete(
                    connection=connection, reason='Team category was deleted, team automatically deleted.'
                )

        # If this channel was the main team's text or voice chat, we need to recreate it
        # and update the metadata that the bot holds.
        if team.text_channel_id == channel.id:
            _log.debug('Team %s text channel was deleted, recreating.', team.display_name)
            new_channel = await category.create_text_channel(name='team-chat')
            await team.edit(text_channel_id=new_channel.id)

            # Notify the team that their chat has been recreated
            notification_embed = self.bot.Embed(
                title='Team Chat Recreated',
                description=f'The team chat for {team.display_name} has been recreated due to it being deleted.',
            )
            await new_channel.send(embed=notification_embed)
            return None
        elif team.voice_channel_id == channel.id:
            _log.debug('Team %s voice channel was deleted, recreating.', team.display_name)
            new_channel = await category.create_voice_channel(name='team-voice')
            return await team.edit(voice_channel_id=new_channel.id)


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Teams(bot))
