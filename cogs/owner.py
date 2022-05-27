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

import re
import sys
import importlib
import importlib.util
import logging
from typing import (
    TYPE_CHECKING,
    Optional,
    List,
)
from typing_extensions import Self

import discord
from discord.ext import commands

from jishaku.shell import ShellReader # type: ignore

from utils import BaseCog
from utils.context import Context, tick
from utils.paginator import AsyncCodePaginator

if TYPE_CHECKING:
    from bot import FuryBot

log = logging.getLogger(__name__)

_GIT_PULL_REGEX: re.Pattern[str] = re.compile(r'(?P<path>(?:[a-z]{1,}/){1,})(?P<filename>[a-z]{1,}).py')


class GitPullSelect(discord.ui.Select['GitPull']):
    """
    A select used by the owner to choose extensions to reload.

    Attributes
    ----------
    extensions: List[:class:`str`]
        A list of extensions to choose from.
    parent: :class:`GitPull`
        The parent GitPull cog.
    """

    def __init__(self, parent: GitPull, /, *, extensions: List[str]) -> None:
        self.extensions: List[str] = extensions
        self.parent: GitPull = parent
        super().__init__(
            placeholder='Select an extension(s) to reload...',
            options=[
                discord.SelectOption(
                    label=extension,
                    emoji='\N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}',
                )
                for extension in extensions
            ],
            max_values=len(extensions),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """|coro|

        The callback for this select. When called, this will reload the selected extensions.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by this select.
        """
        statuses: List[str] = []
        for value in self.values:
            statuses.append(await self.parent._reload_extension(value)) # type: ignore

        await interaction.edit_original_message(content='Reloaded\n' + '\n'.join(statuses), view=None)


class GitPull(discord.ui.View):
    """
    A view to allow the owner to reload extensions after
    pulling from github.

    Attributes
    ----------
    extensions: List[:class:`str`]
        A list of extensions to choose from.
    ctx: :class:`Context`
        The invocation context of the command.
    bot: :class:`FuryBot`
        The bot instance.
    """

    def __init__(self, extensions: List[str], /, *, ctx: Context) -> None:
        super().__init__(timeout=120)

        self.extensions: List[str] = extensions
        self.ctx: Context = ctx
        self.bot: FuryBot = ctx.bot

        for extension_packet in self.bot.chunker(extensions, size=20):  # type: ignore
            extension_packet: List[str]

            self.add_item(GitPullSelect(self, extensions=extension_packet))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """|coro|

        A check called before the interaction is processed.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that is being processed.

        Returns
        -------
        :class:`bool`
            Whether or not the interaction should be processed.
        """
        result = interaction.user == self.ctx.author
        if not result:
            await interaction.response.send_message('Hey! You can\'t do that!')

        return result

    async def _reload_extension(self, extension: str) -> str:
        if extension not in self.bot.extensions:
            try:
                spec = importlib.util.find_spec(extension)
            except ModuleNotFoundError:
                return tick(None, extension)

            if spec is None:
                return tick(None, extension)

            module = importlib.util.module_from_spec(spec)
            sys.modules[extension] = module
            return tick(True, extension)
        else:
            try:
                await self.bot.reload_extension(extension)
            except Exception as exc:
                log.warning(f'Failed to reload extension {extension}.', exc_info=exc)
                return tick(False, f'{extension}: {exc}')

            return tick(True, extension)

    @discord.ui.button(label='Reload All', style=discord.ButtonStyle.green)
    async def reload_all(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """|coro|

        A button used to reload all extensions instead of using the select.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by this button.
        button: :class:`discord.ui.Button`
            The button that was pressed.
        """
        statuses: List[str] = []
        for extension in self.extensions:
            statuses.append(await self._reload_extension(extension))

        await interaction.response.edit_message(content='Reloaded\n' + '\n'.join(statuses), view=None)


class Owner(BaseCog, brief='The Owner commands.', emoji='\N{BLACK SUN WITH RAYS}'):
    """
    The main owner cog. This cog contains commands
    that are only usable by the bot owner.
    """

    async def cog_check(self, ctx: Context) -> bool: # type: ignore
        return await self.bot.is_owner(ctx.author)

    async def git_pull_optimization(self, ctx: Context, buffer: str) -> Optional[discord.Message]:
        matches = _GIT_PULL_REGEX.findall(buffer)
        if not matches:
            return await ctx.send(f'No matches inside the `buffer` were found.')

        extensions: List[str] = []
        for path, filename in matches:
            path = path.replace('/', '.')

            extensions.append(path + filename)

        view = GitPull(extensions, ctx=ctx)
        return await ctx.send(content='Extensions\n' + '\n'.join(f'- {extension}' for extension in extensions), view=view)

    @commands.command(name='git')
    async def git(self, ctx: Context, *, argument: str = 'pull') -> Optional[discord.Message]:
        """|coro|

        Used to perform a git operation and return the output. This is a
        special command, in which if `git pull` is called it will display
        a view to the user to reload any extensions.
        """
        message = await ctx.send('Pulling...')
        await ctx.typing()

        paginator = AsyncCodePaginator(message=message, author=ctx.author, prefix='```py')
        buffer = ''

        with ShellReader(f'git {argument}', loop=self.bot.loop) as reader: # type: ignore
            async for line in reader: # type: ignore
                buffer += f'{line}\n'

        await paginator.add_line(buffer)
        if argument == 'pull':
            return await self.git_pull_optimization(ctx, buffer)


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Owner(bot))
