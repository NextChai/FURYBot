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

from typing import TYPE_CHECKING

from .tracking import Tracker

if TYPE_CHECKING:
    from bot import FuryBot


class InviteTracker(Tracker): ...


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(InviteTracker(bot))
