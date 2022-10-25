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
    Concatenate,
    Coroutine,
    Generator,
    Generic,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)

import discord
from discord.ui.select import BaseSelect, BaseSelectT
from typing_extensions import NotRequired, Self, TypeVarTuple, Unpack

if TYPE_CHECKING:
    from bot import FuryBot

    from .context import Context

__all__: Tuple[str, ...] = ('BaseModal', 'BasicInputModal', 'BaseView', 'BaseViewKwargs', 'AutoRemoveSelect')

ITs = TypeVarTuple("ITs")
T = TypeVar('T')
P = ParamSpec('P')
BT = TypeVar('BT', bound='FuryBot')
TargetType: TypeAlias = Union[
    'discord.Interaction',
    'Context',
]
BaseViewInit: TypeAlias = Callable[Concatenate["BaseView", P], T]

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


class AutoRemoveSelect(BaseSelect['BaseView']):
    """A select that removes all children from its parent and replaces them with itself.
    After the user selects an option, the select is removed and the original children are
    added back to the parent.

    Parameters
    ----------
    parent: :class:`BaseView`
        The parent view of the select.
    calback: Callable[[Any, :class:`discord.Interaction`], Coroutine[Any, Any, Any]]
        The callback to be called when the user selects an option.

    Attributes
    ----------
    parent: :class:`BaseView`
        The parent view of the select.
    """

    def __init__(
        self,
        item: BaseSelectT,
        parent: BaseView,
        callback: Callable[[BaseSelectT, discord.Interaction], Coroutine[Any, Any, Any]],
    ) -> None:
        item.__class__.__name__ = self.__class__.__name__
        item.callback = self.callback

        self.parent: BaseView = parent
        self.item: BaseSelectT = item

        self._callback: Callable[[BaseSelectT, discord.Interaction], Coroutine[Any, Any, Any]] = callback
        self._original_children = parent.children

        parent.clear_items()
        parent.add_item(item)

    async def callback(self, interaction: discord.Interaction) -> Any:
        self.parent.clear_items()
        for child in self._original_children:
            self.parent.add_item(child)

        await self._callback(self.item, interaction)


class BaseModal(discord.ui.Modal):
    def __init__(self, bot: FuryBot, **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        super().__init__(**kwargs)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if self.bot.error_handler:
            return await self.bot.error_handler.log_error(error, origin=interaction, event_name=repr(self))

        return await super().on_error(interaction, error)


class BasicInputModal(BaseModal, Generic[Unpack[ITs]]):
    """A very simple modal that allows other callbacks to wait for its
    completion then manually handle child values.

    Please note this is TypeVarTuple generic, meaning you can do ``BasicInputModal[discord.ui.TextInput[Any], discord.ui.Button[Any]]``
    and the childen will reflect this.
    """

    if TYPE_CHECKING:
        children: Tuple[Unpack[ITs]]

    def __init__(
        self, bot: FuryBot, /, *, after: Callable[[Self, discord.Interaction], Coroutine[Any, Any, Any]], **kwargs: Any
    ) -> None:
        self.after: Callable[..., Coroutine[Any, Any, Any]] = after
        super().__init__(bot, **kwargs)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        await self.after(self, interaction)
        self.stop()


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

    async def callback(self, interaction: discord.Interaction) -> None:
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


class GoHome(discord.ui.Button["BaseView"]):
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

    def __init__(self, parent: BaseView) -> None:
        self.parent: BaseView = parent
        self.bot: FuryBot = parent.bot
        super().__init__(
            label="Go Home",
            emoji=HOME,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """|coro|

        When called, will respond to the interaction by editing the message
        with the view's parent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        await interaction.response.edit_message(view=self.parent, embed=self.parent.embed)


class GoBack(discord.ui.Button["BaseView"]):
    """A button used to go back within the parent tree.

    Attributes
    ----------
    parent: :class:`discord.ui.View`
        The parent view of the help command.
    """

    __slots__: Tuple[str, ...] = ("parent",)

    def __init__(self, parent: discord.ui.View) -> None:
        super().__init__(label="Go Back")
        self.parent: discord.ui.View = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        """|coro|
        When called, will respond to the interaction by editing the message with the previous parent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)  # type: ignore


class BaseViewKwargs(TypedDict):
    target: TargetType
    timeout: NotRequired[Optional[float]]
    parent: NotRequired[BaseView]


class BaseView(discord.ui.View, abc.ABC):
    """A base view that implements the logic that all other views implement.

    Parameters
    ----------
    context: :class:`Context`
        The context of the help command.
    timeout: Optional[:class:`float`]
        The amount of time in seconds before the view times out. Defaults
        to ``120.0``.
    parent: Optional[:class:`discord.ui.View`]
        The parent of this view. Defaults to ``None``.

    Attributes
    ----------
    context: :class:`Context`
        The context of the help command.
    timeout: Optional[:class:`float`]
        The amount of time in seconds before the view times out. Defaults
        to ``120.0``.
    parent: Optional[:class:`discord.ui.View`]
        The parent of this view. Defaults to ``None``.
    """

    __slots__: Tuple[str, ...] = ("bot", "author", "parent", "context")

    def __init_subclass__(cls: Type[Self]) -> None:
        cls.__init__ = _wrap_init(cls.__init__)  # pyright: ignore
        return super().__init_subclass__()

    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        target = kwargs['target']
        if target.guild is None:
            raise ValueError("Cannot create a view in a DM context.")

        self.bot: FuryBot = (
            target.client
            if isinstance(target, discord.Interaction)
            else target.bot  # pyright: ignore # We're gonna have to eat this one, thank you dpy
        )
        self.author: Union[discord.Member, discord.User] = (
            target.user if isinstance(target, discord.Interaction) else target.author
        )
        self.parent: Optional[BaseView] = kwargs.get('parent')
        self.target: TargetType = target
        self.guild: discord.Guild = target.guild
        super().__init__(timeout=kwargs.get('timeout', 120))

    @abc.abstractproperty
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The view's embed to display."""
        raise NotImplementedError

    def _add_menu_children(self) -> None:
        if self.parent is not None:
            self.add_item(GoBack(self.parent))

            home = find_home(self)
            if home and home is not self.parent:
                self.add_item(GoHome(home))

        if not any(isinstance(child, Stop) for child in self.children):
            self.add_item(Stop(self))

    def dump_kwargs(self) -> BaseViewKwargs:
        """BaseViewKwargs: A helper to dump the view's create kwargs when creating a child view."""
        return {'target': self.target, 'timeout': self.timeout, 'parent': self}

    def create_child(self, cls: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Creates a new instance of the view from the parent view."""
        kwargs.update(self.dump_kwargs())
        return cls(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Self]) -> None:
        """|coro|

        A helper to handle errors that occur within the view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the view.
        error: :class:`Exception`
            The error that was raised.
        item: :class:`discord.ui.Item`
            The item that raised the error.
        """
        if self.bot.error_handler:
            return await self.bot.error_handler.exception_manager.add_error(
                error=error, target=interaction, event_name=repr(item)
            )

        return await super().on_error(interaction, error, item)
