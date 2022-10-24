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
import difflib
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Union, cast

import discord
from discord import app_commands

from utils.errors import AutocompleteValidationException

if TYPE_CHECKING:
    from bot import FuryBot

    from .team import Team


@dataclasses.dataclass(init=True, repr=True)
class TeamTransformer(app_commands.Transformer):
    """Represents a transformer that facilitates the selecting of a team.

    Parameters
    ----------
    clamp_teams: :class:`bool`
        If ``True``, this will clamp the available teams based upon
        the team this interaction was created in. For example, if I invoke
        this transformer in a RL team, I'll only see other RL teams
        to select. Defaults to ``False``.
    """

    clamp_teams: bool = dataclasses.field(default=False)

    async def _get_available_teams(
        self, interaction: discord.Interaction, value: Optional[Union[int, float, str]]
    ) -> List[Team]:
        bot: FuryBot = interaction.client  # pyright: ignore
        teams = list(bot.team_cache.values())

        # If we're clamping, we need to return based upon name.
        # If we aren't, we can return all available teams based upon a difflib
        # get close matches result.
        available_teams: List[Team]
        if self.clamp_teams:
            # Get the current team and then extract by name.
            channel = cast(Optional[discord.abc.GuildChannel], interaction.channel)
            if not channel:
                return []

            # Get the team based on the channel now
            invoked_team = discord.utils.find(lambda team: team.has_channel(channel), teams)

            if not invoked_team:
                return []

            # A team name typically looks like this: Rocket League 3, Team Name <Number>.
            # Let's split this to get Rocket League, or Team Name.
            team_name_parsed = ' '.join(invoked_team.name.split()[:-1])

            # Get all teams with similar names now
            available_teams = [team for team in teams if team.name.startswith(team_name_parsed) and team != invoked_team]
        else:
            available_teams = teams

        # Nice, sort by name now base on user input
        if not value:
            return available_teams[:25]
        if not available_teams:
            return []

        team_mapping: Mapping[str, Team] = {team.name: team for team in available_teams}

        similar: List[str] = await bot.wrap(difflib.get_close_matches, value, list(team_mapping.keys()), n=25)  # type: ignore
        return [team_mapping[result] for result in similar]

    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str], /
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        teams = await self._get_available_teams(interaction, value)
        return [app_commands.Choice(name=team.name, value=str(team.id)) for team in teams]

    async def transform(self, interaction: discord.Interaction, value: Any, /) -> Team:
        teams = await self._get_available_teams(interaction, None)

        if not value.isdigit():
            # We have an idiot on our hands who didnt select one
            # of the options... bruh. Check by name now.
            maybe_team = discord.utils.find(lambda team: team.name.lower() == value.lower(), teams)
            if maybe_team:
                return maybe_team

            raise AutocompleteValidationException("You must select a team from the list.")

        maybe_team = discord.utils.find(lambda team: team.id == int(value), teams)
        if not maybe_team:
            raise AutocompleteValidationException("You must select a team from the list.")

        return maybe_team
