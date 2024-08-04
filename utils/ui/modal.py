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

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Optional, Tuple, TypeVar

import discord
from typing_extensions import ParamSpec, Self

if TYPE_CHECKING:
    from bot import FuryBot

T = TypeVar('T')
P = ParamSpec('P')

AfterCallback = Callable[..., Coroutine[Any, Any, Any]]
MISSING = discord.utils.MISSING

__all__: Tuple[str, ...] = ("BaseModal", 'AfterModal')


class BaseModal(discord.ui.Modal):
    """A base modal that all modals should inherit from.

    This handles the :meth:`on_error` callback to send exceptions to the default
    logging handler channel instead of logging to stderr or simiar.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    **kwargs: Any
        Any additional keyword arguments to pass to the :class:`discord.ui.Modal` constructor.
    """

    def __init__(self, bot: FuryBot, **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        super().__init__(**kwargs)

    async def on_error(self, interaction: discord.Interaction[FuryBot], error: Exception) -> None:
        if self.bot.error_handler:
            return await self.bot.error_handler.handle_interaction_error(error=error, interaction=interaction)

        return await super().on_error(interaction, error)


class AfterModal(BaseModal):
    def __init__(
        self,
        bot: FuryBot,
        after: AfterCallback,
        *children: discord.ui.Item[Self],
        title: str = MISSING,
        timeout: Optional[int] = None,
        custom_id: str = MISSING,
        **kwargs: Any,
    ) -> None:
        super().__init__(bot, title=title, timeout=timeout, custom_id=custom_id)
        self._after: AfterCallback = after

        # Remove the unused kwargs we don't pass to the callback
        self._after_kwargs: Dict[str, Any] = kwargs

        self._added_children: Tuple[discord.ui.Item[Self]] = children
        for child in children:
            self.add_item(child)

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> None:
        await self._after(interaction, *self._added_children, **self._after_kwargs)
