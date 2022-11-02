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

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from utils import BaseCog, TimeTransformer

if TYPE_CHECKING:
    from bot import FuryBot


class Owner(BaseCog):
    @app_commands.command()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(value='The value to convert to a time.')
    async def time_transform(
        self, interaction: discord.Interaction, value: app_commands.Transform[TimeTransformer, TimeTransformer('n/a')]
    ) -> None:
        """|coro|

        Transforms the given time input to a human readable format. This is to test the time transformer.

        Parameters
        ----------
        value: :class:`str`
            The value to convert to a time.
        """
        assert value.dt

        embed = self.bot.Embed(
            title='Transformed Time',
            description=f'{discord.utils.format_dt(value.dt, "F")} ({discord.utils.format_dt(value.dt, "R")})',
        )
        embed.add_field(name='Argument', value=value.arg)

        return await interaction.response.send_message(embed=embed)


async def setup(bot: FuryBot):
    await bot.add_cog(Owner(bot))
