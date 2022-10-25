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

import re
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

if TYPE_CHECKING:
    from bot import FuryBot

    # The urlextract lib does not have great type hints. To combat this, we'll create
    # a dummy class that has the required arguments we need.
    class URLExtract:
        if TYPE_CHECKING:

            def find_urls(self, text: str, /) -> List[str]:
                ...

else:
    from urlextract import URLExtract

__all__: Tuple[str, ...] = ('LinkFilter',)


class LinkFilter(URLExtract):
    def __init__(self, bot: FuryBot, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bot: FuryBot = bot
        self._allowed_links: Dict[int, List[str]] = {}

    async def get_links(self, text: str, /, *, guild_id: int) -> List[str]:
        if not self._allowed_links.get(guild_id):
            self._allowed_links[guild_id] = await self.fetch_allowed_links(guild_id)

        links = await self.bot.wrap(self.find_urls, text=text)

        allowed_links = self._allowed_links[guild_id]
        for link in links:
            if any(
                [await self.bot.wrap(re.findall, allowed_link, link) for allowed_link in allowed_links]  # pyright: ignore
            ):
                links.remove(link)

        return links

    async def fetch_allowed_links(self, guild_id: int) -> List[str]:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchval('SELECT valid_links FROM infractions.settings WHERE guild_id = $1', guild_id)

        if data:
            return [l.lower() for l in data]

        return []
