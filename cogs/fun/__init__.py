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
    """|coro|

    The setup function for the cog.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    """
    await bot.add_cog(Fun(bot))
