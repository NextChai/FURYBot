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
from typing import Iterable, Iterator, List, Optional, Tuple

import aiofile
import trieregex

__all__: Tuple[str, ...] = ('GuildProfanityFinder',)


class GuildProfanityFinder:
    """Represents a guild bound profanity filter. Optionally, a Guild ID can not be passed
    to the constructor, and it will be set to None. When it is None, this means the guild does
    not have a custom profanity filter, and the default one will be used.

    Parameters
    Attributes
    ----------
    pattern: :class:`re.Pattern`
        The pattern to use for the profanity filter.
    guild_id: Optional[:class:`int`]
        The guild ID of the guild bound profanity filter. ``None`` for globally
        bound meaning it's the default profanity filter.
    """

    def __init__(self, pattern: re.Pattern[str], *, guild_id: Optional[int] = None) -> None:
        self.pattern: re.Pattern[str] = pattern
        self.guild_id: Optional[int] = guild_id

    @classmethod
    async def get_default_words(cls) -> List[str]:
        async with aiofile.async_open('static/profane_words.txt') as f:
            raw_words = await f.read()

        # Let's split them by ','
        words = raw_words.split(',')

        return words

    @classmethod
    async def get_default_pattern(cls) -> re.Pattern[str]:
        words = await cls.get_default_words()
        return cls.create_pattern_from_words(words)

    @classmethod
    def create_pattern_from_words(cls, words: Iterable[str]) -> re.Pattern[str]:
        tre = trieregex.TrieRegEx(*words)
        return re.compile(f'\\b{tre.regex()}\\b', re.IGNORECASE)

    def finditer(self, string: str) -> Iterator[re.Match[str]]:
        """Finds all matches of the pattern in the string.

        Parameters
        ----------
        string: :class:`str`
            The string to find matches in.

        Returns
        -------
        :class:`re.Match`
            The match object.
        """
        return self.pattern.finditer(string)
