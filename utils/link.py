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

import asyncio
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import trieregex
from urlextract.urlextract_core import URLExtract

if TYPE_CHECKING:
    from bot import FuryBot
    from cogs.links import LinkSettings

__all__: Tuple[str, ...] = ('LinkFilter',)


class LinkFilter(URLExtract):
    def __init__(self, bot: FuryBot, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bot: FuryBot = bot
        self._allowed_items: Dict[int, re.Pattern[str]] = {}

    def build_regex_for_settings(self, settings: LinkSettings) -> None:
        if not settings.allowed_items:
            return

        links = [allowed_item.url for allowed_item in settings.allowed_items]

        tre = trieregex.TrieRegEx(*links)
        self._allowed_items[settings.guild_id] = re.compile(f'\\b{tre.regex()}\\b', re.IGNORECASE)

    def create_allowed_items_regex(self) -> None:
        for setting in self.bot.get_link_settings():
            self.build_regex_for_settings(setting)

    async def fetch_links(self, text: str, /, *, guild_id: Optional[int] = None) -> List[Tuple[str, Tuple[int, int]]]:
        # to_thead here because it's I/O bound
        links = await asyncio.to_thread(self.find_urls, text=text, check_dns=True, get_indices=True)

        if guild_id is None:
            return links

        allowed_items = self._allowed_items.get(guild_id)
        if not allowed_items:
            return links

        for link, (_start, _end) in links:
            matches = await self.bot.wrap(allowed_items.findall, link)
            if matches:
                # We have a match, we need to remove it from the list
                links.remove((link, (_start, _end)))

        return links
