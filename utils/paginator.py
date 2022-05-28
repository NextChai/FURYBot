"""
MIT License

Copyright (c) 2021 NextChai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations
import asyncio

from dataclasses import dataclass
from typing import (
    Optional,
    List,
    Union,
    Any,
    Generic,
    TypeVar,
    TYPE_CHECKING,
    Type,
)
from typing_extensions import Self

import discord
from discord.ext import commands

from jishaku.paginators import WrappedPaginator  # type: ignore

if TYPE_CHECKING:
    from discord.interactions import InteractionChannel

    from .context import Context

    WrappedPaginator = commands.Paginator
else:
    from jishaku.paginators import WrappedPaginator  # type: ignore

T = TypeVar('T')


@dataclass(repr=True, init=True)
class ContextProxy:
    author: Union[discord.Member, discord.User]
    guild: Optional[discord.Guild]
    channel: Optional[InteractionChannel]
    message: Optional[discord.Message] = None


class PaginatorView(discord.ui.View):
    def __init__(
        self,
        paginator: commands.Paginator,
        *,
        timeout: Optional[float] = 180.0,
        author: Optional[Union[discord.Member, discord.User]] = None,
    ) -> None:
        self.paginator: commands.Paginator = paginator
        self.current: int = 0
        self.author: Optional[Union[discord.Member, discord.User]] = author

        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:  # type: ignore
        if not self.author:
            return True

        if self.author == interaction.user:
            return True

        await interaction.response.send_message('Hey! You can\'t do that!', ephemeral=True)
        return False

    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK LEFT-POINTING TRIANGLE}'))
    async def backward(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        self.current -= 1
        try:
            page = self.paginator.pages[self.current]
        except IndexError:
            return await interaction.response.send_message('That\'s the last page!', ephemeral=True)

        return await interaction.response.edit_message(content=page)

    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK RIGHT-POINTING TRIANGLE}'))
    async def forward(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        self.current += 1
        try:
            page = self.paginator.pages[self.current]
        except IndexError:
            return await interaction.response.send_message('That\'s the last page!', ephemeral=True)

        return await interaction.response.edit_message(content=page)

    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{CROSS MARK}'))
    async def stopper(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        await interaction.response.edit_message(view=None)
        await asyncio.sleep(2)
        await interaction.delete_original_message()
        self.stop()


# For imports im commands
class Paginator(WrappedPaginator):
    pass


class IncompletePaginator(Paginator):
    def partially_close_page(self) -> str:
        current = self._current_page.copy()
        if self.suffix is not None:
            current.append(self.suffix)

        return self.linesep.join(current)

    @property
    def incomplete_pages(self) -> List[str]:
        if len(self._current_page) > (0 if self.prefix is None else 1):
            page = self.partially_close_page()
            new_pages = self._pages.copy()
            new_pages.append(page)
            return new_pages

        return self._pages


class BaseButtonPaginator(Generic[T], discord.ui.View):
    """
    The Base Button Paginator class. Will handle all page switching without
    you having to do anything.

    Attributes
    ----------
    entries: List[T]
        A list of entries to get spread across pages.
    per_page: :class:`int`
        The number of entries that get passed onto one page.
    pages: List[List[Any]]
        A list of pages which contain all entries for that page.
    clamp_pages: :class:`bool`
        Whether or not to clamp the pages to the min and max.
    """

    if TYPE_CHECKING:
        ctx: Context

    def __init__(self, *, entries: List[T], per_page: int = 6, clamp_pages: bool = True, **kwargs: Any) -> None:
        super().__init__(timeout=180)
        self.entries: List[T] = entries
        self.per_page: int = per_page
        self.clamp_pages: bool = clamp_pages
        self._orig_kwargs: Any = kwargs

        self._current_page = 0
        self.pages = [entries[i : i + per_page] for i in range(0, len(entries), per_page)]

    @property
    def max_page(self) -> int:
        """:class:`int`: The max page count for this paginator."""
        return len(self.pages)

    @property
    def min_page(self) -> int:
        """:class:`int`: The min page count for this paginator."""
        return 1

    @property
    def current_page(self) -> int:
        """:class:`int`: The current page the user is on."""
        return self._current_page + 1

    @property
    def total_pages(self) -> int:
        """:class:`int`: Returns the total amount of pages."""
        return len(self.pages)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        result = interaction.user == self.ctx.author
        if not result:
            await interaction.response.send_message('Hey! This isn\'t yours!', ephemeral=True)

        return result

    async def format_page(self, entries: List[T], /) -> discord.Embed:
        """|coro|

        Used to make the embed that the user sees.

        Parameters
        ----------
        entries: List[Any]
            A list of entries for the current page.

        Returns
        -------
        :class:`discord.Embed`
            The embed for this page.
        """
        raise NotImplementedError('Subclass did not overwrite format_page coro.')

    def _switch_page(self, count: int, /) -> List[T]:
        self._current_page += count

        if self.clamp_pages:
            if count < 0:  # Going down
                if self._current_page < 0:
                    self._current_page = self.max_page - 1
            elif count > 0:  # Going up
                if self._current_page > self.max_page - 1:  # - 1 for indexing
                    self._current_page = 0

        return self.pages[self._current_page]

    @discord.ui.button(emoji='\U000025c0', style=discord.ButtonStyle.blurple)
    async def on_arrow_backward(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        entries = self._switch_page(-1)
        embed = await self.format_page(entries)
        return await interaction.response.edit_message(embed=embed)

    @discord.ui.button(emoji='\U000025b6', style=discord.ButtonStyle.blurple)
    async def on_arrow_forward(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        entries = self._switch_page(1)
        embed = await self.format_page(entries)
        return await interaction.response.edit_message(embed=embed)

    @discord.ui.button(emoji='\U000023f9', style=discord.ButtonStyle.blurple)
    async def on_stop(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore

        self.stop()

        return await interaction.response.edit_message(view=self)

    @classmethod
    async def start(
        cls: Type[BaseButtonPaginator[T]],
        context: Context,
        *,
        entries: List[T],
        per_page: int = 6,
        clamp_pages: bool = True,
    ) -> BaseButtonPaginator[T]:
        """|coro|

        Used to start the paginator.

        Parameters
        ----------
        context: :class:`commands.Context`
            The context to send to. This could also be discord.abc.Messageable as `ctx.send` is the only method
            used.
        entries: List[T]
            A list of entries to pass onto the paginator.
        per_page: :class:`int`
            A number of how many entries you want per page.

        Returns
        -------
        :class:`BaseButtonPaginator`[T]
            The paginator that was started.
        """
        new = cls(entries=entries, per_page=per_page, clamp_pages=clamp_pages)
        new.ctx = context

        embed = await new.format_page(new.pages[0])
        await context.send(embed=embed, view=new)
        return new

    @classmethod
    async def start_from_interaction(
        cls: Type[BaseButtonPaginator[T]], interaction: discord.Interaction, ephemeral: bool = True, **kwargs: Any
    ) -> BaseButtonPaginator[T]:
        proxy = ContextProxy(
            author=kwargs.get('author') or interaction.user,
            guild=interaction.guild,
            channel=interaction.channel,
            message=None,
        )

        new = cls(**kwargs)
        new.ctx = proxy()  # type: ignore

        embed = await new.format_page(new.pages[0])
        await interaction.response.send_message(embed=embed, view=new, ephemeral=ephemeral)
        return new
