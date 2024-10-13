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

from typing import TYPE_CHECKING, Callable, List, Mapping, Tuple

import discord
from discord import app_commands

from utils import AutocompleteValidationException

if TYPE_CHECKING:
    from bot import FuryBot

    from .team import Team

    _process_extract: Callable[..., List[Tuple[str, int]]]
else:
    from fuzzywuzzy.process import extract as _process_extract


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

    def __init__(self, clamp_teams: bool = False) -> None:
        self.clamp_teams: bool = clamp_teams

    @property
    def type(self) -> discord.AppCommandOptionType:
        return discord.AppCommandOptionType.integer

    @staticmethod
    def _get_similar_teams(interaction: discord.Interaction[FuryBot]) -> List[Team]:
        # A helper to get all teams that are similar to the team this command was invoked on.
        # This will only be called if clamp_teams is True.
        channel = interaction.channel
        if channel is None or isinstance(channel, discord.PartialMessageable):
            # dpy couldn't resolve this channel (maybe not in cache?)
            return []

        guild = channel.guild
        if guild is None:
            return []

        guild_teams = interaction.client.get_teams(guild.id)
        team = discord.utils.find(lambda team: team.has_channel(channel.id), guild_teams)
        if not team:
            # This command wasn't invoked in a team chat
            return []

        # Great, now let's get all similar teams matching the teams name.
        team_name_parsed = ' '.join(team.name.split()[:-1])  # Turns "Rocket League 1" to "Rocket League"

        return [t for t in guild_teams if team_name_parsed in t.name and t != team]

    async def autocomplete(self, interaction: discord.Interaction[FuryBot], value: str) -> List[app_commands.Choice[int]]:
        """|coro|

        Transforms the user's input that they're typing to a list of recommended choices based upon

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the user typing.
        value: :class:`str`
            The value that the user is typing.
        """
        guild = interaction.guild
        if guild is None:
            # This command can't be used in DMS
            return []

        bot: FuryBot = interaction.client

        # If we're clamping the teams, we need to get the similar teams to use.
        if self.clamp_teams:
            similar_teams = self._get_similar_teams(interaction)
        else:
            similar_teams = bot.get_teams(guild.id)

        # Great, now let's use this list with fuzzy matching to get more similar teams.
        team_name_mapping: Mapping[str, Team] = {team.name: team for team in similar_teams}
        team_names = list(team_name_mapping.keys())

        # Get the top 10 teams with similar names as to what the user is typing
        similar: List[Tuple[str, int]] = await bot.wrap(_process_extract, value, team_names, limit=10)

        # Now let's create a list of choices for the user to select from.
        choices: List[app_commands.Choice[int]] = []

        for team_name, _ in similar:
            team = team_name_mapping[team_name]
            choices.append(app_commands.Choice(name=team.display_name, value=team.id))

        return choices

    async def transform(self, interaction: discord.Interaction[FuryBot], value: int, /) -> Team:  # skipcq: PYL-R0201
        """|coro|

        Transforms the given users input to a team.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the user invoking the command.
        value: :class:`int`
            The value that the user selected.
        """
        guild = interaction.guild
        if not guild:
            raise AutocompleteValidationException('This command can only be used in a server.')

        team = interaction.client.get_team(value, guild_id=guild.id)
        if team is None:
            raise AutocompleteValidationException('User did not select a valid team.')

        return team
