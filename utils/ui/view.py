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
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Optional,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

import discord
from discord.ext import commands
from typing_extensions import Concatenate, NotRequired, ParamSpec, Self, TypeAlias, Unpack

if TYPE_CHECKING:
    from bot import FuryBot

    from ..context import Context

__all__: Tuple[str, ...] = (
    'ViewMixin',
    'BaseViewKwargs',
    'BaseView',
    'BaseAsyncView',
    'PaginatorView',
    'walk_parents',
    'AfterConfirmation',
)

T = TypeVar('T')
P = ParamSpec('P')
BT = TypeVar('BT', bound='FuryBot')
TargetType: TypeAlias = Union['discord.Interaction[FuryBot]', 'Context']
ViewMixinInit: TypeAlias = Callable[Concatenate["ViewMixin", P], T]
ViewMixinT = TypeVar('ViewMixinT', bound='ViewMixin')

QUESTION_MARK = "\N{BLACK QUESTION MARK ORNAMENT}"
HOME = "\N{HOUSE BUILDING}"
NON_MARKDOWN_INFORMATION_SOURCE = "\N{INFORMATION SOURCE}"


def _wrap_init(__init__: ViewMixinInit[P, T]) -> ViewMixinInit[P, T]:
    """A decorator used to wrap the init of an existing
    child view's __init__ method, and then add the
    "Stop", "Go home", and "Go Back" buttons **always last**.
    """

    @functools.wraps(__init__)
    def wrapped(self: ViewMixin, *args: P.args, **kwargs: P.kwargs) -> T:
        result = __init__(self, *args, **kwargs)
        self._add_menu_children()
        return result

    return wrapped


def walk_parents(view: ViewMixin) -> Generator[ViewMixin, None, None]:
    """Walk through the parents of a view, yielding each parent."""

    parent = view.parent
    while parent:
        parent = view.parent
        if not parent:
            break

        view = parent

        yield parent


def find_home(view: ViewMixin) -> Optional[ViewMixin]:
    """A method to find the home parent from a view."""
    parents = list(walk_parents(view))
    if not parents:
        return

    return parents[-1]


class _OptionalViewMixinKwargs(TypedDict):
    timeout: NotRequired[Optional[float]]
    parent: NotRequired[ViewMixin]


class BaseViewKwargs(_OptionalViewMixinKwargs):
    target: TargetType


class Stop(discord.ui.Button["ViewMixin"]):
    """A button used to stop the help command.

    Attributes
    ----------
    parent: :class:`discord.ui.View`
        The parent view of the help command.
    """

    __slots__: Tuple[str, ...] = ("parent",)

    def __init__(self, parent: ViewMixin) -> None:
        self.parent: ViewMixin = parent
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


class GoHome(discord.ui.Button[ViewMixinT], Generic[ViewMixinT]):
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

    def __init__(self, parent: ViewMixinT) -> None:
        self.parent: ViewMixinT = parent
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
        embed = self.parent._get_embed()
        if inspect.iscoroutine(embed):
            embed = await embed

        assert isinstance(embed, discord.Embed)
        await interaction.response.edit_message(view=self.parent, embed=embed)


class GoBack(discord.ui.Button["ViewMixin"], Generic[ViewMixinT]):
    """A button used to go back within the parent tree.

    Attributes
    ----------
    parent: :class:`discord.ui.View`
        The parent view of the help command.
    """

    __slots__: Tuple[str, ...] = ("parent",)

    def __init__(self, parent: ViewMixinT) -> None:
        super().__init__(label="Go Back")
        self.parent: ViewMixinT = parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        """|coro|
        When called, will respond to the interaction by editing the message with the previous parent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by interacting with the button.
        """
        embed = self.parent._get_embed()
        if inspect.iscoroutine(embed):
            embed = await embed

        return await interaction.response.edit_message(embed=embed, view=self.parent)  # type: ignore


class ViewMixin(discord.ui.View, abc.ABC):
    """A base view that implements the logic that all other views implement.

    Parameters
    ----------
    context: Union[:class:`Context`, :class:`DummyContext`]
        The context of the help command.
    timeout: Optional[:class:`float`]
        The amount of time in seconds before the view times out. Defaults
        to ``120.0``.
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
        self.parent: Optional[ViewMixin] = kwargs.get('parent')
        self.target: TargetType = target
        self.guild: discord.Guild = target.guild
        super().__init__(timeout=kwargs.get('timeout', 120))

    def _add_menu_children(self) -> None:
        if self.parent is not None:
            self.add_item(GoBack(self.parent))

            home = find_home(self)
            if home and home is not self.parent:
                self.add_item(GoHome(home))

        if not any(isinstance(child, Stop) for child in self.children):
            self.add_item(Stop(self))

    @abc.abstractmethod
    def _get_embed(self) -> Union[discord.Embed, Coroutine[Any, Any, discord.Embed]]:
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
        if self.bot.error_handler:
            return await self.bot.error_handler.exception_manager.add_error(
                error=error, target=interaction, event_name=repr(item)
            )

        return await super().on_error(interaction, error, item)


class BaseView(ViewMixin):
    """Represents a base view with a non-async embed property."""

    @property
    @abc.abstractmethod
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The view's embed to display."""
        raise NotImplementedError

    def _get_embed(self) -> discord.Embed:
        return self.embed


class BaseAsyncView(ViewMixin):
    """Represents a base view with an async embed method."""

    @abc.abstractmethod
    async def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The view's embed to display."""
        ...

    def _get_embed(self) -> Coroutine[Any, Any, discord.Embed]:
        return self.embed()


class PaginatorView(BaseView):
    """Represents a Paginator View. This class will wrap around a paginator
    and allow for buttons to interact between the pages of this paginator.

    Parameters
    ----------
    paginator: :class:`commands.Paginator`
        The paginator to wrap around.
    **kwargs: Any
        The kwargs to pass to the :class:`ViewMixin` constructor.

    Attributes
    ----------
    paginator: :class:`commands.Paginator`
        The paginator to wrap around.
    current: :class:`int`
        The current index of the page that is being displayed.
    """

    def __init__(self, paginator: commands.Paginator, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.paginator: commands.Paginator = paginator
        self.current: int = 0

        super().__init__(**kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: Although not used, this property is required by the ABC."""
        raise NotImplementedError

    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK LEFT-POINTING TRIANGLE}'))
    async def backward(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """|coro|

        Used to go backwards on the paginator view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from pressing the button.
        button: :class:`discord.ui.Button`
            The button that was pressed.
        """
        self.current -= 1
        try:
            page = self.paginator.pages[self.current]
        except IndexError:
            return await interaction.response.send_message('That\'s the last page!', ephemeral=True)

        return await interaction.response.edit_message(content=page)

    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK RIGHT-POINTING TRIANGLE}'))
    async def forward(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """|coro|

        Used to go forward on the paginator view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from pressing the button.
        button: :class:`discord.ui.Button`
            The button that was pressed.
        """
        self.current += 1
        try:
            page = self.paginator.pages[self.current]
        except IndexError:
            return await interaction.response.send_message('That\'s the last page!', ephemeral=True)

        return await interaction.response.edit_message(content=page)


class AfterConfirmation(BaseView):
    def __init__(
        self,
        after: Callable[[discord.Interaction[FuryBot], Optional[bool]], Coroutine[Any, Any, Any]],
        **kwargs: Unpack[BaseViewKwargs],
    ) -> None:
        self.after: Callable[[discord.Interaction[FuryBot], Optional[bool]], Coroutine[Any, Any, Any]] = after
        self.value: Optional[bool] = None
        super().__init__(**kwargs)

    @property
    def embed(self) -> discord.Embed:
        return self.bot.Embed(
            title='Confirmation',
            description='Are you sure you want to do this?',
        )

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """|coro|

        Called when the "Confirm" button has been clicked. When called, this will set the internal :attr:`value` to True
        and close the view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction[FuryBot]`
            The interaction that triggered the button.
        button: :class:`discord.ui.Button`
            The button that was clicked.
        """
        self.value = True
        self.stop()
        await self.after(interaction, self.value)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """|coro|

        Called when the "Cancel" button has been clicked. When called, this will set the internal :attr:`value` to False
        and close the view.

        Parameters
        ----------
        interaction: :class:`discord.Interaction[FuryBot]`
            The interaction that triggered the button.
        button: :class:`discord.ui.Button`
            The button that was clicked.
        """
        self.value = False
        self.stop()
        await self.after(interaction, self.value)
