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


class CannotCreateScrim(Exception):
    """Raised when a scrim cannot be created."""

    def __str__(self) -> str:
        return "Cannot create scrim."


class NoHomeTeamTextChannel(CannotCreateScrim):
    """Raised when there is no home team text channel."""

    def __str__(self) -> str:
        return "No home team text channel."
