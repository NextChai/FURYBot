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

from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands

from utils import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot


class Moderation(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

        cleanup_context_command = app_commands.ContextMenu(
            name='Cleanup 10 Messages',
            type=discord.AppCommandType.message,
            callback=self.cleanup_10_messages_context_command_callback,
        )
        self.bot.tree.add_command(cleanup_context_command)

    @app_commands.command(name='nick', description='Nick a member.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member='The member to change the nick for.', nick='The nick to use. Do not include for no nick.')
    async def nick(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member, nick: Optional[str] = None
    ) -> None:
        await member.edit(nick=nick)
        return await interaction.response.send_message(
            f'I\'ve updated the nickname on {member.mention} to `{nick}`', ephemeral=True
        )

    @app_commands.command(name='assign', description='Assign a role to a member.')
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(member='The member to assign the role to.', role='The role to assign.')
    async def assign(self, interaction: discord.Interaction[FuryBot], member: discord.Member, role: discord.Role) -> None:
        await member.add_roles(role)
        return await interaction.response.send_message(f'I\'ve assigned {role.mention} to {member.mention}', ephemeral=True)

    async def _cleanup_n_messages(
        self,
        interaction: discord.Interaction[FuryBot],
        to: discord.Member,
        n: int,
        location: Optional[discord.abc.MessageableChannel] = None,
    ) -> discord.InteractionMessage:
        await interaction.response.defer(ephemeral=True)
        if location is None:
            if interaction.channel is None:
                return await interaction.edit_original_response(
                    content='Could not obtain the channel you requested, try again later or in a different channel.'
                )

            location = interaction.channel  # type: ignore # Technically an interaction channel qualifies this constraint.

        # TODO: Finish this
        raise

    @app_commands.command(name='cleanup', description='Cleanup messages from a user in a channel.')
    @app_commands.rename(location='in', n='amount')
    @app_commands.describe(
        to='The member to cleanup messages from.',
        location='The channel to cleanup messages in.',
        n='The amount of messages to cleanup.',
    )
    async def cleanup(
        self,
        interaction: discord.Interaction[FuryBot],
        to: discord.Member,
        n: int,
        location: Optional[discord.abc.MessageableChannel],
    ) -> discord.InteractionMessage:
        return await self._cleanup_n_messages(interaction, to, n, location)

    async def cleanup_10_messages_context_command_callback(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        return await self._cleanup_n_messages(interaction, member, 10, None)


async def setup(bot: FuryBot):
    await bot.add_cog(Moderation(bot))
