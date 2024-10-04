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


class TeamException(Exception):
    """The base exception all team exceptions inherit from."""


class MemberNotOnTeam(TeamException):
    """Exception raised when a member is not on a team."""


class TeamNotFound(TeamException):
    """Exception raised when a team is not found."""


class TeamDeleted(TeamException):
    def __init__(self, *, team_id: int) -> None:
        super().__init__(f'Team with id {team_id} has been deleted.', team_id)
        self.team_id: int = team_id
