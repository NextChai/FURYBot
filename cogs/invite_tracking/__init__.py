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

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from utils import RUNNING_DEVELOPMENT

from .tracking import Tracker

if TYPE_CHECKING:
    from bot import FuryBot

_log = logging.getLogger(__name__)
if RUNNING_DEVELOPMENT:
    _log.setLevel(logging.DEBUG)


class InviteTracker(Tracker):
    @commands.Cog.listener('on_invite_update')
    async def on_invite_update(self, member: discord.Member, invite: discord.Invite) -> None:
        """
        Called when a member has joined a given guild using an invite.

        Updates the invite in the tracking database.

        """
        _log.debug('Invite %s updated', invite.code)

        uses = invite.uses
        if not uses:
            _log.debug('Invite %s has no uses, cannot do anything.', invite.code)
            return

        guild = member.guild
        inviter = invite.inviter
        if not inviter:
            # For some reason, the person who created this invite, the inviter, is not available.
            # All we can do is try and make an update in the database (if this invite is being tracked)
            # and return. We cannot insert a new entry
            _log.debug('Fallback to updating invite %s in the database', invite.code)

            async with self.bot.safe_connection() as connection:
                await connection.execute(
                    """
                    UPDATE invite_tracker.invites
                    SET uses = $1
                    WHERE guild_id = $2 AND invite_code = $3;
                    """,
                    uses,
                    guild.id,
                    invite.code,
                )

            return

        # Update the invite in the tracking DB
        _log.debug('Updating invite %s in the database for uses %s', invite.code, uses)
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO invite_tracker.invites (
                    guild_id,
                    user_id,
                    invite_code,
                    created_at,
                    expires_at,
                    uses
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (guild_id, invite_code) DO UPDATE
                SET uses = EXCLUDED.uses;
                """,
                guild.id,
                inviter.id,
                invite.code,
                invite.created_at,
                invite.expires_at,
                uses,
            )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(InviteTracker(bot))
