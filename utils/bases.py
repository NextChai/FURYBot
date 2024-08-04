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

from typing import TYPE_CHECKING, Optional, Protocol, Tuple

if TYPE_CHECKING:
    import discord

    from bot import FuryBot
    from cogs.teams.team import Team, TeamMember

__all__: Tuple[str, ...] = ('Guildable', 'Teamable', 'Botable', 'TeamMemberable')


class Botable(Protocol):
    def _get_bot(self) -> FuryBot: ...


class Guildable(Botable, Protocol):
    def _get_guild_id(self) -> int: ...

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self._get_bot().get_guild(self._get_guild_id())


class Teamable(Guildable, Protocol):
    def _get_team_id(self) -> int: ...

    @property
    def team(self) -> Team:
        team = self._get_bot().get_team(self._get_team_id(), guild_id=self._get_guild_id())
        assert team
        return team


class TeamMemberable(Teamable, Protocol):
    def _get_member_id(self) -> int: ...

    @property
    def team_member(self) -> Optional[TeamMember]:
        return self.team.get_member(self._get_member_id())

    @property
    def mention(self) -> str:
        member_id = self._get_member_id()
        return f'<@{member_id}>'
