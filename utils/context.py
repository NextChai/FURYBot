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

from typing import TYPE_CHECKING, Optional, TypeAlias, Union

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import FuryBot

Context: TypeAlias = 'commands.Context[FuryBot]'


class DummyContext:
    """A dummy context constructed to get a :class:`commands.Context` like object
    from an interaction when interaction command data is not complete.

    Parameters
    ----------
    interaction: :class:`discord.Interaction`
        The interaction to transform into :class:`DummyContext`.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The main bot instance.
    guild: Optional[:class:`discord.Guild`]
        The guild this interaction was created in. ``None`` for no guild.
    channel: Optional[:class:`discord.interactions.InteractionChannel`]
        The channel this interaction was invoked in.
    author: Union[:class:`discord.Member`, :class:`discord.User`]
        The author of this interaction instance.
    """

    def __init__(self, interaction: discord.Interaction) -> None:
        self.bot: FuryBot = interaction.client  # pyright: ignore
        self.guild: Optional[discord.Guild] = interaction.guild
        self.channel: Optional[discord.interactions.InteractionChannel] = interaction.channel
        self.author: Union[discord.User, discord.Member] = interaction.user
