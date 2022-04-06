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
import cachetools
import asyncio
import asyncache 
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

PROFANITY_CHACHE = cachetools.Cache(maxsize=1024)

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
    
    def __init__(self, *, swears: Iterable[str]):
        self._swears: List[str] = list(swears)

    @property
    def swears(self) -> List[str]:
        """List[:class:`str`]: Returns the current list of swears."""
        return self._swears
    
    def permeate_swears(self) -> List[str]:
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
        self.profanity_cache = cachetools.Cache(maxsize=1024)
        self.safe_connection: Callable[[], AsyncContextManager[Connection]] = safe_connection
        
        asyncache.cached(cache=self.profanity_cache, lock=asyncio.Lock())(self.get_profane_words)
        
    async def get_profanity(self) -> List[str]:
        async with self.safe_connection() as connection:
            data = await connection.fetch('SELECT word FROM profanity')
        
        return PermeateProfanity(swears=[element['word'] for element in data]).permeate_swears()
    
    async def get_profane_words(self) -> List[str]:
        profane = []
        
        if not self._profanity:
            self._profanity = await self.get_profanity()
        
        if self._profanity:
            profane.extend(self._profanity)
            profane.extend(inflection.pluralize(word) for word in self._profanity)
            
        profane = list(set(profane)) # Clean duplicates
        profane.sort(key=len)
        profane.reverse()
        
        for word in profane:
            for invalid in self.invalid_regex:
                word = word.replace(invalid, r'\{0}'.format(invalid))
        
        return profane
    
    async def censor(self, text: str, *, fast: bool = False) -> str:
        """Returns input_text with any profane words censored."""
        profane = await self.get_profane_words()
        
        def _wrapped(text: str, *, fast: bool = False) -> str:
            res = text

            for word in profane:
                # Apply word boundaries to the bad word
                regex_string = r'\b{0}\b'.format(word)
                res = re.sub(regex_string, self._censor_char * len(word), res)
                
                if res != text and fast:
                    return res

            return res
        
        return await self.wrap(_wrapped, text=text, fast=fast)