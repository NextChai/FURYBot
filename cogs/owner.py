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

import sys
import importlib
from typing import TYPE_CHECKING, Dict, Optional, List

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, TimeTransformer, Context

if TYPE_CHECKING:
    from bot import FuryBot


class Owner(BaseCog):
    @app_commands.command(description='Transform some time.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(value='The value to convert to a time.')
    @app_commands.guild_only()
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

    @commands.command(name='reload')
    @commands.is_owner()
    async def _reload(self, ctx: Context, force_importlib: Optional[bool] = False, *extensions: str) -> discord.Message:
        """Reload the given extensions.

        Parameters
        ----------
        force_importlib: :class:`bool`
            Whether to force the use of importlib to reload extensions
            that are also bot extensions. This will be used to refresh
            any classes in the module before loading the extension.
        *extensions: :class:`str`
            The extensions to reload.
        """
        statuses: Dict[str, Optional[Exception]] = {}
        for extension in extensions:
            if extension in self.bot.extensions:
                try:
                    if force_importlib:
                        sys.modules[extension] = importlib.reload(sys.modules[extension])

                    await self.bot.reload_extension(extension)
                    statuses[extension] = None
                except Exception as exc:
                    statuses[extension] = exc
            else:

                try:
                    sys.modules[extension] = importlib.reload(sys.modules[extension])
                    statuses[extension] = None
                except Exception as exc:
                    statuses[extension] = exc

        response: List[str] = []
        for extension, exception in statuses.items():
            if exception is not None:
                if self.bot.error_handler:
                    await self.bot.error_handler.log_error(exception, origin=ctx, event_name=self._reload.qualified_name)

                response.append(f'`{extension}`: Failed to reload: **{exception}**')
            else:
                response.append(f'`{extension}`: Reloaded successfully.')

        return await ctx.send('\n'.join(response))


async def setup(bot: FuryBot):
    await bot.add_cog(Owner(bot))
