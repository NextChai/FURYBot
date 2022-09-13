from __future__ import annotations

from typing import TYPE_CHECKING, Any, Tuple

import discord
from typing_extensions import Self

if TYPE_CHECKING:
    from bot import FuryBot


class BaseModal(discord.ui.Modal):
    def __init__(self, bot: FuryBot, **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        super().__init__(**kwargs)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if self.bot.error_handler:
            return await self.bot.error_handler.exception_manager.add_error(
                error=error, target=interaction, event_name=repr(self)
            )

        return await super().on_error(interaction, error)


class InputModal(BaseModal):
    def __init__(self, bot: FuryBot, *args: discord.ui.TextInput[Self], **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        self.added_children: Tuple[discord.ui.TextInput[Self]] = args
        super().__init__(bot=bot, **kwargs)

        for item in args:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        return await super().on_submit(interaction)
