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

from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Generic, List, ParamSpec, Tuple, TypeAlias, TypeVar, Union

import discord
from discord.app_commands import AppCommandChannel, AppCommandThread

if TYPE_CHECKING:
    from bot import FuryBot

    from .view import BaseView

__all__: Tuple[str, ...] = ('ChannelSelect', 'UserSelect', 'RoleSelect', 'MentionableSelect', 'SelectOneOfMany')

T = TypeVar('T')
P = ParamSpec('P')
ItemT = TypeVar('ItemT', bound='discord.ui.Item[Any]')
SFT = TypeVar('SFT', bound='discord.abc.Snowflake')
SFTC = TypeVar('SFTC', bound='discord.abc.Snowflake', contravariant=True)
ViewMixinT = TypeVar('ViewMixinT', bound='BaseView')
AfterCallback: TypeAlias = Callable[[discord.Interaction['FuryBot'], List[T]], Any]


class CleanupSelectHelper(Generic[ViewMixinT], discord.ui.Item[ViewMixinT]):
    """A helper class to manage the cleanup of a select. This dynamically removes
    all children from its parent and adds them back when the select is closed.
    """

    def __init__(self, parent: ViewMixinT, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._parent: ViewMixinT = parent
        self._original_children: List[discord.ui.Item[ViewMixinT]] = parent.children
        self._parent.clear_items()
        self._parent.add_item(self)
        super().__init__(*args, **kwargs)

    def _readd_children(self) -> Any:
        self._parent.clear_items()
        for child in self._original_children:
            self._parent.add_item(child)


class SelectOneOfMany(Generic[ViewMixinT]):
    """A helper class to manage the cleanup of a select. This dynamically removes
    all children from the parent, and then readds them when the select is closed.

    Parameters
    ----------
    parent: :class:`BaseView`
        The parent view to add the select to.
    options: List[:class:`discord.SelectOption`]
        The options to add to the select.
    after: Callable[[:class:`discord.Interaction`, List[:class:`str`]], Coroutine]
        The callback to call when the select is closed.
    placeholder: :class:`str`
        The placeholder to use for the select.
    max_values: :class:`int`
        The maximum number of values that can be selected.
    """

    def __init__(
        self,
        parent: ViewMixinT,
        /,
        *,
        options: List[discord.SelectOption],
        after: Callable[[discord.Interaction[FuryBot], List[str]], Coroutine[Any, Any, Any]],
        placeholder: str = 'Select one...',
        max_values: int = 1,
    ) -> None:
        self._parent: ViewMixinT = parent
        self._original_children: List[discord.ui.Item[ViewMixinT]] = parent.children
        self._parent.clear_items()

        self._after: Callable[[discord.Interaction[FuryBot], List[str]], Coroutine[Any, Any, Any]] = after

        self.options: List[discord.SelectOption] = options
        for chunk in discord.utils.as_chunks(self.options, 25):
            select: discord.ui.Select[ViewMixinT] = discord.ui.Select(
                options=chunk, placeholder=placeholder, max_values=max_values
            )
            select.callback = partial(self._select_callback, select=select)
            self._parent.add_item(select)

    async def _select_callback(
        self, interaction: discord.Interaction[FuryBot], select: discord.ui.Select[ViewMixinT]
    ) -> None:
        self._parent.clear_items()
        for child in self._original_children:
            self._parent.add_item(child)

        values = select.values
        await self._after(interaction, values)


class RelaySelect(Generic[T, ViewMixinT], CleanupSelectHelper[ViewMixinT], discord.ui.Item[ViewMixinT]):
    """A helper class that will redirect the callback of a select to a different callback.
    This is so we can dynamically handle the callback of a select without having to subclass
    it every time and create repeat code.

    You should never manually create an instance of this class.

    The following classes implement this:

    - :class:`ChannelSelect`
    - :class:`RoleSelect`
    - :class:`UserSelect`
    - :class:`MentionableSelect`

    Example
    -------
    .. code-block:: python3

        class MyView(BaseView):
            async def channel_select_after(self, interaction: discord.Interaction, values: List[Channel], item: ChannelSelect) -> None:
                ...

            @discord.ui.button(label="Click me for a select!")
            async def launch_select(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
                select = ChannelSelect(after=self.channel_select_after)
                await respond(view=self)
    """

    def __init__(self, after: AfterCallback[T], parent: ViewMixinT, *args: Any, **kwargs: Any) -> None:
        self.after: AfterCallback[T] = after
        self._parent: ViewMixinT = parent
        super().__init__(parent, *args, **kwargs)

    @property
    def view(self) -> ViewMixinT:
        return self._parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        self._readd_children()
        # It's hard to annotate that this class has access to a "values" property,
        # and that args and kwargs are the correct type. It's MUCH easier to type ignore
        # this and leave it than it is to try and fix it.
        await self.after(interaction, self.values)  # type: ignore


class ChannelSelect(
    RelaySelect[Union[AppCommandChannel, AppCommandThread], ViewMixinT],
    discord.ui.ChannelSelect[ViewMixinT],
):
    """Allows an after parameter to be passed to the callback of a channel select. Optionally,
    you can pass additional args and kwargs to be passed to the callback.
    """

    def __init__(
        self,
        after: AfterCallback[Union[AppCommandChannel, AppCommandThread]],
        parent: ViewMixinT,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(after, parent, *args, **kwargs)


class RoleSelect(Generic[ViewMixinT], RelaySelect[discord.Role, ViewMixinT], discord.ui.RoleSelect[ViewMixinT]):
    """Allows an after parameter to be passed to the callback of a role select. Optionally,
    you can pass additional args and kwargs to be passed to the callback.
    """

    def __init__(self, after: AfterCallback[discord.Role], parent: ViewMixinT, *args: Any, **kwargs: Any) -> None:
        super().__init__(after, parent, *args, **kwargs)


class UserSelect(
    RelaySelect[Union[discord.Member, discord.User], ViewMixinT],
    discord.ui.UserSelect[ViewMixinT],
):
    """Allows an after parameter to be passed to the callback of a user select. Optionally,
    you can pass additional args and kwargs to be passed to the callback.
    """

    def __init__(
        self,
        after: AfterCallback[Union[discord.Member, discord.User]],
        parent: ViewMixinT,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(after, parent, *args, **kwargs)


class MentionableSelect(
    RelaySelect[Union[discord.Member, discord.User, discord.Role], ViewMixinT],
    discord.ui.MentionableSelect[ViewMixinT],
):
    """Allows an after parameter to be passed to the callback of a mentionable select. Optionally,
    you can pass additional args and kwargs to be passed to the callback.
    """

    def __init__(
        self,
        after: AfterCallback[Union[discord.Member, discord.User, discord.Role]],
        parent: ViewMixinT,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(after, parent, *args, **kwargs)
