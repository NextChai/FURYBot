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
import importlib.util
import logging
from typing import TYPE_CHECKING, Any, List, Sequence, Optional

import discord
from discord.ext import commands

from utils import BaseCog
from utils.context import Context, tick
from utils.paginator import Paginator, PaginatorView
from utils.shell import AsyncShellExecutor

if TYPE_CHECKING:
    from bot import FuryBot

log = logging.getLogger(__name__)

GIT_PULL_REGEX: re.Pattern[str] = re.compile(r'(?P<path>(?:[a-z]{1,}/){1,})(?P<filename>[a-z]{1,}).py')
GIT_REPO_REGEX: re.Pattern[str] = re.compile(
    r'https://github.com/(?P<owner>[\w\-\.]+)/(?P<repo>[\w\-\.]+)/([\w\-\.]+)/(?P<branch>[\w\-]+)(?P<path>(?:/[\w\.\-]{1,}){1,})(?:#L(?P<opening>[0-9]+)(?:\-L(?P<closing>[0-9]+))?)?',
    flags=re.IGNORECASE,
)


async def _reload_extension(bot: FuryBot, extension: str) -> str:
    if extension not in bot.extensions:
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
            await bot.reload_extension(extension)
        except Exception as exc:
            log.warning(f'Failed to reload extension {extension}.', exc_info=exc)
            return tick(False, f'{extension}: {exc}')

        return tick(True, extension)


class GitPullSelect(discord.ui.Select['GitPullSelect']):
    """
    A select used by the owner to choose extensions to reload.

    Attributes
    ----------
    extensions: List[:class:`str`]
        A list of extensions to choose from.
    parent: :class:`GitPull`
        The parent GitPull cog.
    """

    def __init__(self, bot: FuryBot, /, *, extensions: Sequence[str], **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        self.extensions: Sequence[str] = extensions
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
            **kwargs,
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
        for extension in self.extensions:
            statuses.append(await self.parent._reload_extension(extension))  # type: ignore

        await interaction.edit_original_message(content='Reloaded\n' + '\n'.join(statuses), view=None)


class ReloadAll(discord.ui.Button[Any]):
    def __init__(self, bot: FuryBot, *, extensions: List[str], **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        self.extensions: List[str] = extensions
        super().__init__(label='Reload All', style=discord.ButtonStyle.green, **kwargs)

    async def callback(self, interaction: discord.Interaction) -> Any:
        statuses: List[str] = []
        for extension in self.extensions:
            statuses.append(await _reload_extension(self.bot, extension))

        await interaction.response.edit_message(content='Reloaded\n' + '\n'.join(statuses), view=None)


class Github(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

    @commands.group(
        name='git',
        brief='Perform github actions and use the github API.',
        description='Perform github actions and use the github API.',
        aliases=['github'],
    )
    async def github(self, ctx: Context, *, argument: str = 'pull') -> Optional[discord.Message]:
        if ctx.invoked_subcommand:
            return

    @github.command(
        name='pull',
        brief='Pull from github.',
        description='Pull from github.',
    )
    async def github_pull(self, ctx: Context) -> Optional[discord.Message]:
        """|coro|

        Used to perform a git operation and return the output. This is a
        special command, in which if `git pull` is called it will display
        a view to the user to reload any extensions.
        """
        await ctx.typing()

        paginator = Paginator(prefix='```python')
        buffer = ''

        async with AsyncShellExecutor(f'git pull') as reader:  # type: ignore
            line: Optional[str]
            async for line in reader:
                buffer += f'{line}\n'

        paginator.add_line(buffer)

        extensions: List[str] = []
        matches = GIT_PULL_REGEX.findall(buffer)
        if matches:
            extensions = [path.replace('/', '.') + filename for (path, filename) in matches]
            paginator.prefix = 'Extensions\n' + '\n'.join(f'- {extension}' for extension in extensions) + '\n```python'
        else:
            paginator.prefix = f'No matches found from github regex.\n```python'

        view = PaginatorView(paginator, timeout=180, author=ctx.author)
        if matches:
            for extension_packet in self.bot.chunker(extensions, size=20):
                view.add_item(GitPullSelect(self.bot, extensions=extension_packet))  # type: ignore

            view.add_item(ReloadAll(self.bot, extensions=extensions))

        await ctx.send(content=paginator.pages[0], view=view)


class Owner(Github, brief='The Owner commands.', emoji='\N{BLACK SUN WITH RAYS}'):
    """
    The main owner cog. This cog contains commands
    that are only usable by the bot owner.
    """

    async def cog_check(self, ctx: Context) -> bool: # type: ignore
        return await self.bot.is_owner(ctx.author)

    


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Owner(bot))
