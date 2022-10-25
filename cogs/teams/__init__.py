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

from typing import TYPE_CHECKING, TypeAlias

import discord
from discord import app_commands

from utils import BaseCog, TimeTransformer

from .scrim import Scrim
from .team import Team
from .transformers import TeamTransformer
from .views import TeamView

if TYPE_CHECKING:
    from bot import FuryBot


TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer]
FRONT_END_TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer(clamp_teams=True)]


class Teams(BaseCog):
    """A cog to manage teams and allow teams to create scrims and find subs."""

    team = app_commands.Group(
        name='team',
        description='Create and manage teams.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    scrim = app_commands.Group(name='scrim', description='Create and manage scrims.', guild_only=True)
    subs = app_commands.Group(name='subs', description='Find a sub for your games.', guild_only=True)

    @team.command(name='create', description='Create a team.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(name='The name of the team.')
    async def team_create(self, interaction: discord.Interaction, name: str) -> discord.InteractionMessage:
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
    async def team_manage(self, interaction: discord.Interaction, team: TEAM_TRANSFORM) -> discord.InteractionMessage:
        """|coro|

        A command used to manage a team. This will launch an depth view in which you can manage the team.

        Use this command to add subs, remove subs, add members, remove members, create extra channels, assign captain roles,
        etc.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to manage.
        """
        await interaction.response.defer()

        view = TeamView(team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @scrim.command(name='create', description='Create a scrim')
    @app_commands.describe(
        team='The team you want to scrim against.',
        when='When you want to scrim the other team. For ex: "Tomorrow at 4pm", "Next tuesday at 12pm", etc.',
        per_team='The amount of players per team. For ex: 5, 3, 2, etc.',
    )
    async def scrim_create(
        self,
        interaction: discord.Interaction,
        team: FRONT_END_TEAM_TRANSFORM,
        when: TimeTransformer,
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
        assert when.dt

        await interaction.response.defer(ephemeral=True)

        home_team = Team.from_category(interaction.channel.category.id, bot=self.bot)

        scrim = await Scrim.create(
            when.dt, home_team=home_team, away_team=team, per_team=per_team, creator_id=interaction.user.id, bot=self.bot
        )

        return await interaction.edit_original_response(
            content=f'A scrim for {scrim.scheduled_for_formatted()} has been created against {team.name}).'
        )


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
