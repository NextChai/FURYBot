"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to
non-commercial purposes. Distribution, sublicensing, and sharing of this file
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not
misrepresent the original material. This license does not grant any
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
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
            return await self.bot.error_handler.handle_tree_on_error(error=error, interaction=interaction)

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

        self._added_children: Tuple[discord.ui.Item[Self]] = children  # type: ignore
        for child in children:
            self.add_item(child)

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> None:
        await self._after(interaction, *self._added_children, **self._after_kwargs)
