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
    from bot import ConnectionType, FuryBot

__all__: Tuple[str, ...] = ('LinkFilter',)


class LinkFilter(URLExtract):
    def __init__(self, bot: FuryBot, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bot: FuryBot = bot
        self._allowed_links: Dict[int, re.Pattern[str]] = {}

    async def load_allowed_links_cache(self, *, connection: ConnectionType) -> None:
        data = await connection.fetch(
            'SELECT *, (SELECT guild_id FROM links.settings WHERE id = settings_id) as guild_id FROM links.allowed_links'
        )

        allowed_links: Dict[int, List[str]] = {}
        for entry in data:
            allowed_links.setdefault(entry['guild_id'], []).append(entry['link'])

        for guild_id, links in allowed_links.items():
            tre = trieregex.TrieRegEx(*links)
            self._allowed_links[guild_id] = re.compile(f'\\b{tre.regex()}\\b', re.IGNORECASE)

    async def fetch_links(self, text: str, /, *, guild_id: Optional[int] = None) -> List[Tuple[str, Tuple[int, int]]]:
        # to_thead here because it's I/O bound
        links = await asyncio.to_thread(self.find_urls, text=text, check_dns=True, get_indices=True)

        if guild_id is None:
            return links

        allowed_links = self._allowed_links.get(guild_id)
        if not allowed_links:
            return links

        for link, (_start, _end) in links:
            matches = await self.bot.wrap(allowed_links.findall, link)
            if matches:
                # We have a match, we need to remove it from the list
                links.remove((link, (_start, _end)))

        return links
