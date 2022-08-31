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
from typing import TYPE_CHECKING, ClassVar, Dict, List, NamedTuple, Optional, Tuple

import cachetools
import inflection

if TYPE_CHECKING:
    from bot import FuryBot


class ProfanityWord(NamedTuple):
    """Represents a profanity word.

    Although not implemented now, there's plans to extend the functionality
    of this class and implement new features - such as aliases.

    Parameters
    ----------
    word: :class:`str`
        The word that is profane.

    Attributes
    ----------
    word: :class:`str`
        The word that is profane.
    """

    word: str


class ProfantiyFilter:
    """A class to manage detecting phrases that contain profanity.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The main bot instance.

    Attributes
    -----------
    bot: :class:`FuryBot`
        The main bot instance.
    profanity_mapping: Dict[:class:`str`, :class:`ProfanityWord`]
        A mapping of base word to class :class:`ProfanityWord`.
    profanity_hashing: Dict[:class:`int`, :class:`str`]
        A hash map of hashed phrases to their censored version.
    """

    invalid_regex_characters: ClassVar[Tuple[str, ...]] = ('.', '^', '$', '.', '+')

    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.profanity_mapping: Dict[str, ProfanityWord] = {}
        self.profanity_hashing: cachetools.LRUCache[int, str] = cachetools.LRUCache(maxsize=5000)
        self._profanity_regex: Optional[re.Pattern[str]] = None

    async def fetch_profane_words(self) -> List[str]:
        """|coro|

        List[:class:`str`]: Fetches all the profane words from the database,
        """
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT word FROM profane_words')

        return [entry['word'] for entry in data]

    async def build_profanity_mapping(self, words: List[str], /) -> Dict[str, ProfanityWord]:
        """|coro|

        A helper method to build the :attr:`profanity_mapping`

        Parameters
        ----------
        words: List[:class:`str`]
            A list of words to build the mapping with.

        Returns
        -------
        Dict[:class:`str`, :class:`ProfanityWord`]
            A mapping of base word to class :class:`ProfanityWord`.
        """
        words.extend(w.replace('er', 'a') for w in words if w.endswith('er'))  # er -> a

        plural = [self.bot.wrap(inflection.pluralize, word) for word in words]
        words.extend(await asyncio.gather(*plural))

        for word in words:
            if any(invalid in word for invalid in self.invalid_regex_characters):
                for invalid in self.invalid_regex_characters:
                    word = word.replace(invalid, r'\{0}'.format(invalid))

        words = list(set(words))
        words.sort(key=len, reverse=True)

        self.profanity_mapping = mapping = {word: ProfanityWord(word) for word in words}
        return mapping

    def _subber(self, match: re.Match[str]) -> str:
        result = match.group(0)
        if result.lower() not in self.profanity_mapping:
            return result

        return '*' * len(match.group(0))

    async def censor(self, phrase: str) -> str:
        """|coro|

        A coroutine to censor profanity from a string.

        Parameters
        ----------
        phrase: :class:`str`
            The phrase to censor.

        Returns
        -------
        :class:`str`
            The censored phrase.
        """
        if cached := self.profanity_hashing.get(hash(phrase)):
            return cached

        if not self._profanity_regex:
            words = await self.fetch_profane_words()
            mapping = await self.build_profanity_mapping(words)
            self._profanity_regex = re.compile('|'.join(mapping.keys()), flags=re.IGNORECASE)

        subbed = self._profanity_regex.sub(self._subber, phrase)
        if any('*' in char and not '*' * len(char) == char for char in subbed.split()):
            return phrase

        return subbed
