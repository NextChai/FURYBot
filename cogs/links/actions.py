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

import datetime
import enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import discord

if TYPE_CHECKING:
    from bot import FuryBot


class LinkActionType(enum.Enum):
    warn = 1
    mute = 2
    surpress = 3


class LinkAction:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.settings_id: int = data['settings_id']
        self.type: LinkActionType = LinkActionType(data['type'])
        self.delta: Optional[datetime.timedelta] = datetime.timedelta(seconds=delta) if (delta := data['delta']) else None
        self.warn_message: Optional[str] = data['warn_message']

    @property
    def settings(self) -> Optional[LinkSettings]:
        return discord.utils.get(self.bot.get_link_settings(), id=self.settings_id)


class LinkSettings:
    def __init__(self, *, bot: FuryBot, data: Dict[str, Any]) -> None:
        self.bot: FuryBot = bot
        self.id: int = data['id']
        self.guild_id: int = data['guild_id']
        self.notifier_channel_id: Optional[int] = data['notifier_channel_id']
        self.actions: List[LinkAction] = [LinkAction(bot=bot, data=action) for action in data['actions']]

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def notifier_channel(self) -> Optional[discord.abc.GuildChannel]:
        if self.notifier_channel_id is None:
            return None

        guild = self.guild
        if guild is None:
            return None

        return guild.get_channel(self.notifier_channel_id)
