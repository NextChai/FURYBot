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
import inflection
import asyncio
from typing import (
    TYPE_CHECKING,
    AsyncContextManager,
    Awaitable,
    Callable, 
    ClassVar,
    Dict, 
    Iterable, 
    List, 
    Optional, 
    Tuple,
    TypeVar,
    Any
)
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from asyncpg import Connection

__all__: Tuple[str, ...] = (
    'PermeateProfanity',
    'ProfanityChecker'
)

T = TypeVar('T')
P = ParamSpec('P')


class PermeateProfanity:
    """A helper class used to permeate a list of swear words into all possible combinations.
    
    This is mainly used so cheeky members in the server who use profanity can be caught easily.
    """
    mapping: ClassVar[Dict[str, List[str]]] = {
        'a': ['@'],
        'i': ['!', 'l', '1'],
        'd': ['b'],
        't': ['7'],
        'o': ['0'],
        's': ['$'],
        'y': ['i', 'ie']
    }  
    
    def __init__(self, *, swears: Iterable[str]) -> None:
        self._swears: List[str] = list(swears)

    @property
    def swears(self) -> List[str]:
        """List[:class:`str`]: Returns the current list of swears."""
        return self._swears
    
    async def permeate_swears(self) -> List[str]:
        """|coro|
        
        Used to fill up all possible combinations of a swear word.
        
        For example, `soysauce` would turn into: 'soysauce', '$oysauce', '$0ysauce', '$0isauce', etc.
        """
        for swear in self._swears:
            if swear.endswith('er'): 
                self._swears.append(swear.replace('er', 'a')) 
                
            for index, char in enumerate(swear):
                current = self.mapping.get(char.lower())
                if not current:
                    continue
                
                for switch in current:
                    formatted = swear[0:index] + switch + swear[index+1:]
                    self._swears.append(formatted) # type: ignore
                break 
            
        return self._swears
            
            
class ProfanityChecker:
    """The base profanity filter for the bot.
    
    .. note::
    
        :meth:`ProfanityChecker.get_profane_words` is overwritten so a whitelist can be used.
        
    Attributes
    ----------
    clean_wordset: List[:class:`str`]
        The clean wordset of the bot, aka the whitelisted words.
    extra_profanity: List[:class:`str`]
        The bad words of the bot, aka the words that will get flagged.
    """
    
    invalid_regex = (
        '.',
        '^',
        '$',
        '.'
    )
    
    def __init__(self, *, wrap: Callable[..., Awaitable[Any]], safe_connection: Callable[[], AsyncContextManager[Connection]]) -> None:
        self._profanity: Optional[List[str]] = None
        self._censor_char = '*'
        self.wrap: Callable[..., Awaitable[Any]] = wrap
        self.safe_connection: Callable[[], AsyncContextManager[Connection]] = safe_connection
        self._profanity_lock: asyncio.Lock = asyncio.Lock()
        self._profanity_regex: Optional[re.Pattern] = None
        self._database_profanity: Optional[List[str]] = None
        
    async def _get_profanity(self) -> List[str]:
        async with self.safe_connection() as connection:
            data = await connection.fetch('SELECT word FROM profanity')
        
        return await PermeateProfanity(swears=[element['word'] for element in data]).permeate_swears()
    
    async def get_profane_words(self) -> List[str]:
        """|coro|
        
        A coroutine to get a complete list of profane word and return it, as 
        well as setting some internal markers for later use.
        
        Returns
        -------
        List[:class:`str`]
            The list of profane words.
        """
        async with self._profanity_lock:
            if self._profanity:
                return self._profanity
            
            profanity = await self._get_profanity()
            self._database_profanity = profanity

            plural = [self.wrap(inflection.pluralize, word) for word in profanity]
            profanity.extend(await asyncio.gather(*plural))
            
            profanity = list(set(profanity)) # Clean duplicates
            profanity.sort(key=len)
            profanity.reverse()
            
            for word in profanity:
                for invalid in self.invalid_regex:
                    word = word.replace(invalid, r'\{0}'.format(invalid))
            
            self._profanity = profanity
            return profanity
        
    def _subber(self, match: re.Match) -> str:
        return self._censor_char * len(match.group(0))
    
    async def censor(self, text: str) -> str:
        """Returns input_text with any profane words censored."""
        if not self._profanity_regex:
            profane = await self.get_profane_words()
            self._profanity_regex = re.compile('|'.join(profane), flags=re.IGNORECASE)
        
        return await self.wrap(self._profanity_regex.sub, self._subber, text)