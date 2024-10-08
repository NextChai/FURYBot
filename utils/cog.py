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

from typing import TYPE_CHECKING, Tuple

from discord.ext import commands

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('BaseCog',)


class BaseCog(commands.Cog):
    """Implementation for a base cog class. This class is meant to be inherited from,
    instead of directly inheriting :class:`commands.Cog`. This is so if you don't have a unique
    :meth:`__init__` you don't have you add it.

    .. note::
        Down the road this will also hold special methods that all cogs can access.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.

    Attributes
    ----------
    bot: :class:`Bot`
        The bot instance.
    """

    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
