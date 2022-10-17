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

import difflib
from typing import TYPE_CHECKING, Any, List, Optional, TypeAlias, Union

import discord
from discord import app_commands

from utils.bases.cog import BaseCog
from utils.errors import BadArgument

from .team import Team

if TYPE_CHECKING:
    from bot import FuryBot


class TeamTransformer(app_commands.Transformer):
    def __init__(self, /, *, lock_team_type: Optional[bool] = None) -> None:
        self.lock_team_type: Optional[bool] = lock_team_type

    def _get_similar_teams(self, bot: FuryBot, channel_id: int) -> List[Team]:
        # Find the team first
        team = discord.utils.get(bot.team_cache.values(), text_channel_id=channel_id)
        if team is None:
            return []

        teams: List[Team] = []
        name = [e.lower() for e in team.name.split(' ')[:-1]]
        for local_team in bot.team_cache.values():
            c_name = [e.lower() for e in local_team.name.split(' ')[:-1]]
            if c_name == name and local_team is not team:
                teams.append(local_team)

        return teams

    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str], /
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        assert interaction.channel

        bot: FuryBot = interaction.client  # type: ignore

        team_mapping = {
            team.name: team
            for team in (
                self._get_similar_teams(bot, interaction.channel.id) if self.lock_team_type else bot.team_cache.values()
            )
        }

        if not team_mapping:
            return []

        if not value or self.lock_team_type:
            return [app_commands.Choice(name=team.name, value=str(team.id)) for team in team_mapping.values()]

        similar: List[str] = await bot.wrap(difflib.get_close_matches, str(value), team_mapping.keys(), n=20)  # type: ignore

        first = similar[0]
        first_team = team_mapping[first]
        if first == first_team.name:
            return [app_commands.Choice(name=first_team.name, value=str(first_team.id))]

        return [app_commands.Choice(name=team_mapping[entry].name, value=str(team_mapping[entry].id)) for entry in similar]

    async def transform(self, interaction: discord.Interaction, value: Any, /) -> Team:
        bot: FuryBot = interaction.client  # type: ignore

        if not value.isdigit():
            # Try and locate from name
            for team in bot.team_cache.values():
                if team.name.lower() == value.lower():
                    return team

            raise BadArgument(interaction, 'You did not select one of the team options.')

        return bot.team_cache[int(value)]


TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer]
FRONT_END_TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer(lock_team_type=True)]


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


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
