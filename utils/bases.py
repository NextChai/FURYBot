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

from typing import TYPE_CHECKING, Optional, Protocol, Tuple

if TYPE_CHECKING:
    import discord

    from bot import FuryBot
    from cogs.teams.team import Team, TeamMember

__all__: Tuple[str, ...] = ('GuildAble', 'TeamAble', 'Botable', 'TeamMemberAble')


class Botable(Protocol):
    def _get_bot(self) -> FuryBot: ...


class GuildAble(Botable, Protocol):
    def _get_guild_id(self) -> int: ...

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self._get_bot().get_guild(self._get_guild_id())


class TeamAble(GuildAble, Protocol):
    def _get_team_id(self) -> int: ...

    @property
    def team(self) -> Team:
        team = self._get_bot().get_team(self._get_team_id(), guild_id=self._get_guild_id())
        assert team
        return team


class TeamMemberAble(TeamAble, Protocol):
    def _get_member_id(self) -> int: ...

    @property
    def team_member(self) -> Optional[TeamMember]:
        return self.team.get_member(self._get_member_id())

    @property
    def mention(self) -> str:
        member_id = self._get_member_id()
        return f'<@{member_id}>'
