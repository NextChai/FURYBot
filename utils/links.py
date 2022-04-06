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
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    List,
    Optional,
)

from urlextract import URLExtract

if TYPE_CHECKING:
    from asyncpg import Connection

_LINK_REGEX: re.Pattern = re.compile(
    r'\b('
    r'(?:https?://)?'
    r'(?:(?:www\.)?(?:[\da-z\.-]+)\.(?:[a-z]{2,6})'
    r'|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
    r'|(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|'
    r'(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|'
    r'(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|'
    r'[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|'
    r'fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|'
    r'(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|'
    r'(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|'
    r'(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])))'
    r'(?::[0-9]{1,4}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])'
    r'?(?:/[\w\.-]*)*/?)\b'
)


class LinkChecker(URLExtract):
    def __init__(
        self, 
        *args, 
        wrap: Callable[..., Awaitable[Any]],
        safe_connection: Callable[..., AsyncContextManager[Connection]],
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.wrap: Callable[..., Awaitable[Any]] = wrap
        self.safe_connection: Callable[..., AsyncContextManager[Connection]] = safe_connection
        
        self._allowed_links: Optional[List[str]] = None
        
    async def get_links(self, text: str) -> List[Any]:
        return await self.wrap(self.find_urls, text=text)

    async def contains_links(self, text: str) -> bool:
        return await self.get_links(text) != []
    
    async def fetch_allowed_links(self) -> List[str]:
        async with self.safe_connection() as connection:
            data = await connection.fetch('SELECT url FROM links')
            
        return [element['url'] for element in data]
        
    async def is_valid_link(self, link: str) -> bool:
        if not self._allowed_links:
            self._allowed_links = await self.fetch_allowed_links()
            
        return link in self._allowed_links