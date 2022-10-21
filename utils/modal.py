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
