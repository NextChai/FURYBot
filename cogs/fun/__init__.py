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

import io
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, Context

from .typing_test import TypingTestView

if TYPE_CHECKING:
    from bot import FuryBot


class Fun(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot=bot)

    @commands.hybrid_command(name='typing-test', description='Test your typing speed!')
    async def typing_test(self, ctx: Context) -> None:
        async with ctx.typing():
            view = TypingTestView(ctx=ctx)
            view.remove_stop_button()
            message = await ctx.send(view=view, embed=view.embed)
            view.message = message

    @app_commands.command(name='avatar', description='Get the avatar of a user.')
    @app_commands.describe(member='The member to get the avatar of.')
    async def avatar(
        self, interaction: discord.Interaction[FuryBot], member: Optional[discord.Member] = None
    ) -> discord.InteractionMessage:
        """|coro|

        Gets the avatar of a user.

        Parameters
        ----------
        member: Optional[:class:`discord.Member`]
            The member to get the avatar of. Defaults to the author.
        """
        await interaction.response.defer()
        target = member or interaction.user

        avatar = await target.display_avatar.read()

        filename = f'{target.display_name}_avatar.png'
        file = discord.File(
            fp=io.BytesIO(avatar),
            filename=f'{target.display_name}_avatar.png',
            description=f'Avatar of {target.display_name}',
        )

        embed = self.bot.Embed(title=f'{target.display_name} Avatar')
        embed.set_image(url=f'attachment://{filename}')
        return await interaction.edit_original_response(embed=embed, attachments=[file])


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Fun(bot))
