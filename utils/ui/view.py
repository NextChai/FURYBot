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

import abc
import functools
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Hashable,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

import discord
from typing_extensions import Concatenate, NotRequired, ParamSpec, Self, TypeAlias, Unpack

if TYPE_CHECKING:
    from bot import FuryBot

    from ..context import Context

__all__: Tuple[str, ...] = ('BaseViewKwargs', 'BaseView', 'walk_parents', 'MultiSelector', 'find_home')

T = TypeVar('T')
P = ParamSpec('P')
BT = TypeVar('BT', bound='FuryBot')
TargetType: TypeAlias = Union['discord.Interaction[FuryBot]', 'Context']
BaseViewInit: TypeAlias = Callable[Concatenate["BaseView", P], T]
BaseViewT = TypeVar('BaseViewT', bound='BaseView')

QUESTION_MARK = "\N{BLACK QUESTION MARK ORNAMENT}"
HOME = "\N{HOUSE BUILDING}"
NON_MARKDOWN_INFORMATION_SOURCE = "\N{INFORMATION SOURCE}"


def _wrap_init(__init__: BaseViewInit[P, T]) -> BaseViewInit[P, T]:
    """A decorator used to wrap the init of an existing
    child view's __init__ method, and then add the
    "Stop", "Go home", and "Go Back" buttons **always last**.
    """

    @functools.wraps(__init__)
    def wrapped(self: BaseView, *args: P.args, **kwargs: P.kwargs) -> T:
        result = __init__(self, *args, **kwargs)
        self._add_menu_children()
        return result

    return wrapped


def walk_parents(view: BaseView) -> Generator[BaseView, None, None]:
    """Walk through the parents of a view, yielding each parent."""

    parent = view.parent
    while parent:
        parent = view.parent
        if not parent:
            break

        view = parent

        yield parent


def find_home(view: BaseView) -> Optional[BaseView]:
    """A method to find the home parent from a view."""
    parents = list(walk_parents(view))
    if not parents:
        return

    return parents[-1]


class _OptionalViewMixinKwargs(TypedDict):
    timeout: NotRequired[Optional[float]]
    parent: NotRequired[Optional[BaseView]]


class BaseViewKwargs(_OptionalViewMixinKwargs):
    target: TargetType


class Stop(discord.ui.Button["BaseView"]):
    """A button used to stop the help command.

    Attributes
    ----------
    parent: :class:`discord.ui.View`
        The parent view of the help command.
    """

    __slots__: Tuple[str, ...] = ("parent",)

    def __init__(self, parent: BaseView) -> None:
        self.parent: BaseView = parent
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Stop",
        )

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|
        When called, will respond to the interaction by editing the message
        with the diabled view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        for child in self.parent.children:
            child.disabled = True  # type: ignore

        self.parent.stop()
        return await interaction.response.edit_message(view=self.parent)


class GoHome(discord.ui.Button[BaseViewT], Generic[BaseViewT]):
    """A button used to go home within the parent tree. Home
    is considered the root of the parent tree.

    Attributes
    ----------
    parent: Any
        The parent of the help command.
    bot: :class:`FuryBot`
        The bot that the help command is running on.
    """

    __slots__: Tuple[str, ...] = (
        "parent",
        "bot",
    )

    def __init__(self, parent: BaseViewT) -> None:
        self.parent: BaseViewT = parent
        self.bot: FuryBot = parent.bot
        super().__init__(
            label="Go Home",
            emoji=HOME,
        )

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|

        When called, will respond to the interaction by editing the message
        with the view's parent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        await interaction.response.edit_message(view=self.parent, embed=self.parent.embed)


class GoBack(discord.ui.Button["BaseView"], Generic[BaseViewT]):
    """A button used to go back within the parent tree.

    Attributes
    ----------
    parent: :class:`discord.ui.View`
        The parent view of the help command.
    """

    __slots__: Tuple[str, ...] = ("parent",)

    def __init__(self, parent: BaseViewT) -> None:
        super().__init__(label="Go Back")
        self.parent: BaseViewT = parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|
        When called, will respond to the interaction by editing the message with the previous parent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class BaseView(discord.ui.View, abc.ABC):
    """A base view that implements the logic that all other views implement.

    Parameters
    ----------
    context: Union[:class:`Context`, :class:`DummyContext`]
        The context of the help command.
    timeout: Optional[:class:`float`]
        The amount of time in seconds before the view times out. Defaults
        to ``360.0``.
    parent: Optional[:class:`discord.ui.View`]
        The parent of this view. Defaults to ``None``.

    Attributes
    ----------
    context: Union[:class:`Context`, :class:`DummyContext`]
        The context of the help command.
    timeout: Optional[:class:`float`]
        The amount of time in seconds before the view times out. Defaults
        to ``120.0``.
    parent: Optional[:class:`discord.ui.View`]
        The parent of this view. Defaults to ``None``.
    """

    __slots__: Tuple[str, ...] = ("bot", "author", "parent", "context")

    def __init_subclass__(cls: Type[Self]) -> None:
        if cls.__name__ in ('BaseView', 'BaseAsyncView'):
            return super().__init_subclass__()

        cls.__init__ = _wrap_init(cls.__init__)  # pyright: ignore
        return super().__init_subclass__()

    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        target = kwargs['target']
        if target.guild is None:
            raise ValueError("Cannot create a view in a DM context.")

        self.bot: FuryBot = target.client if isinstance(target, discord.Interaction) else target.bot
        self.author: Union[discord.Member, discord.User] = (
            target.user if isinstance(target, discord.Interaction) else target.author
        )
        self.parent: Optional[BaseView] = kwargs.get('parent')
        self.target: TargetType = target
        self.guild: discord.Guild = target.guild
        super().__init__(timeout=kwargs.get('timeout', 360))

    def _add_menu_children(self) -> None:
        children_cls = {type(child) for child in self.children}
        if self.parent is not None:
            if GoBack not in children_cls:
                self.add_item(GoBack(self.parent))

            home = find_home(self)
            if home and home is not self.parent and GoHome not in children_cls:
                self.add_item(GoHome(home))

        if Stop not in children_cls:
            self.add_item(Stop(self))

    @abc.abstractproperty
    def embed(self) -> discord.Embed:
        ...

    def dump_kwargs(self) -> BaseViewKwargs:
        """ViewMixinKwargs: A helper to dump the view's create kwargs when creating a child view."""
        return {'target': self.target, 'timeout': self.timeout, 'parent': self}

    def create_child(self, cls: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Creates a new instance of the view from the parent view."""
        kwargs.update(self.dump_kwargs())
        return cls(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> bool:
        """|coro|

        Called when the interaction is created. If the user is not the author of the message,
        it will alert the user and return ``False``.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the view.

        Returns
        -------
        :class:`bool`
            Whether the interaction should be allowed.
        """
        check = self.author == interaction.user

        if not check:
            await interaction.response.send_message("Hey, you can't do that!", ephemeral=True)

        return check

    async def on_error(
        self, interaction: discord.Interaction[FuryBot], error: Exception, item: discord.ui.Item[Self]
    ) -> None:
        await self.bot.error_handler.exception_manager.add_error(
            error=error, target=interaction, event_name=repr(item)
        )

        return await super().on_error(interaction, error, item)


class _ChooseItemModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        parent: MultiSelector[BaseViewT, Any],
        modal_title: str = 'Choose Item',
        modal_item: Optional[discord.ui.TextInput[_ChooseItemModal]] = None,
    ) -> None:
        super().__init__(title=modal_title, timeout=None)
        self.parent: MultiSelector[BaseViewT, Any] = parent

        self.item = modal_item or discord.ui.TextInput(
            label='Choose Item', placeholder='Choose the item from it\'s given hash.'
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> Any:
        # It's assumed that the user was shown the hash from the item sooo they can type it in.
        # We can get the item now?
        item = self.parent.items_mapping.get(self.item.value)
        if item is None:
            await self.parent.launch(interaction)
            return await interaction.followup.send(
                'I could not find that item in this list. Please try again.', ephemeral=True
            )

        return await self.parent.on_item_chosen(interaction, item)


class _ChooseItemButton(discord.ui.Button[BaseViewT]):
    def __init__(
        self,
        *,
        parent: MultiSelector[BaseViewT, Any],
    ) -> None:
        super().__init__(label='Choose Item', style=discord.ButtonStyle.green)
        self.parent: MultiSelector[BaseViewT, Any] = parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        modal = _ChooseItemModal(parent=self.parent)
        return await interaction.response.send_modal(modal)


class _PageManagerButton(discord.ui.Button[BaseViewT]):
    def __init__(self, parent: MultiSelector[BaseViewT, Any], action: Literal['increment', 'decrement']) -> None:
        super().__init__(label=f'{action.title()} Page', style=discord.ButtonStyle.blurple)

        self.parent: MultiSelector[BaseViewT, Any] = parent
        self.action: Literal['increment', 'decrement'] = action

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> Any:
        # We need to increment or decrement the current page based on the action, but we need to make sure
        # We don't go out of range of the pages.

        if self.action == 'increment':
            if self.parent.current_page == self.parent.max_page:
                # Go to there first page.
                self.parent.current_page = 0
            else:
                self.parent.current_page += 1
        else:
            if self.parent.current_page == 0:
                # Go to the last page.
                self.parent.current_page = self.parent.max_page
            else:
                self.parent.current_page -= 1

        items = self.parent.current_items
        embed = self.parent.create_embed(items)
        return await interaction.response.edit_message(embed=embed)


class MultiSelector(Generic[BaseViewT, T], abc.ABC):
    def __init__(
        self,
        *,
        parent: BaseViewT,
        items: List[T],
        per_page: int = 10,
        modal_title: str = 'Choose Item',
        modal_item: Optional[discord.ui.TextInput[_ChooseItemModal]] = None,
    ) -> None:
        self.modal_title: str = modal_title
        self.modal_item: Optional[discord.ui.TextInput[_ChooseItemModal]] = modal_item

        self.parent: BaseViewT = parent
        self._original_children: List[discord.ui.Item[BaseViewT]] = parent.children

        self.items_mapping: Dict[Hashable, T] = {self.hash_item(item): item for item in items}
        self.pages = [items[i : i + per_page] for i in range(0, len(items), per_page)]
        self.per_page: int = per_page
        self.current_page: int = 0

        parent.clear_items()

        if len(self.pages) >= 1:
            parent.add_item(_PageManagerButton(parent=self, action='decrement'))
            parent.add_item(_PageManagerButton(parent=self, action='increment'))

        parent.add_item(_ChooseItemButton(parent=self))

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def max_page(self) -> int:
        return self.total_pages - 1

    @property
    def current_items(self) -> List[T]:
        return self.pages[self.current_page]

    @abc.abstractmethod
    def create_embed(self, items: Iterable[T]) -> discord.Embed:
        ...

    @abc.abstractmethod
    def hash_item(self, item: T) -> Hashable:
        ...

    @abc.abstractmethod
    async def on_item_chosen(self, interaction: discord.Interaction[FuryBot], item: T) -> Any:
        ...

    async def launch(self, interaction: discord.Interaction[FuryBot]) -> None:
        # Get information from the first page
        items = self.current_items
        embed = self.create_embed(items)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self.parent)
        else:
            await interaction.response.edit_message(embed=embed, view=self.parent)
