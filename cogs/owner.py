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

import dataclasses
import importlib.util
import importlib.machinery
import logging
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, List

import discord
from discord.ext import commands

from utils import Context, BaseCog

if TYPE_CHECKING:
    from bot import FuryBot

_log = logging.getLogger(__name__)


@dataclasses.dataclass()
class ReloadStatus:
    module: str
    statuses: List[Any] = dataclasses.field(default_factory=list)
    exceptions: List[BaseException] = dataclasses.field(default_factory=list)


class Owner(BaseCog):
    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    def _reload_extension(self, extension: str, module: ModuleType) -> None:
        sys.modules[extension] = module

    def _is_discordpy_extension(self, spec: importlib.machinery.ModuleSpec, module: ModuleType) -> bool:
        spec.loader.exec_module(module)  # type: ignore
        return bool(getattr(module, 'setup', None))

    @commands.command(name='reload', description='Reload a module or extension.', aliases=['rl', 'load'])
    async def reload_modules(self, ctx: Context, *modules: str) -> discord.Message:
        async with ctx.typing():
            statuses: Dict[str, ReloadStatus] = {}
            for module_name in modules:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    statuses[module_name] = ReloadStatus(
                        module=module_name,
                        exceptions=[commands.errors.ExtensionNotFound(module_name)],
                        statuses=[ctx.tick(False, f'Could not find module_name from name `{module_name}`.')],
                    )
                    continue

                module = importlib.util.module_from_spec(spec)
                status = ReloadStatus(module=module_name)

                self._reload_extension(module_name, module)
                status.statuses.append(f'Reloaded module `{module_name}` successfully.')

                is_dpy_extension = self._is_discordpy_extension(spec, module)
                if is_dpy_extension is False:
                    status.statuses.append('Discord.py setup method not found.')
                    continue

                status.statuses.append('Discord.py setup method detected.')
                try:
                    if module_name in self.bot.extensions:
                        await self.bot.reload_extension(module_name)
                    else:
                        await self.bot.load_extension(module_name)
                except Exception as exc:
                    status.exceptions.append(exc)
                    status.statuses.append('Failed to reload module, unknown exception occured.')

                status.statuses.append(ctx.tick(True, label='Reloaded entire module without problems.'))
                statuses[module_name] = status

            embed = self.bot.Embed(description='# Reload Statuses')
            for module_name, status in statuses.items():
                for exception in status.exceptions:
                    await self.bot.error_handler.log_error(
                        exception, origin=ctx, event_name=f'reload-command-fail:{module_name}'
                    )

                embed.add_field(
                    name=module_name, value='\n'.join(map(lambda status: f'- {status}', status.statuses)), inline=False
                )

        return await ctx.send(embed=embed)


async def setup(bot: FuryBot):
    await bot.add_cog(Owner(bot))
