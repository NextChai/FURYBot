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
    Generic, 
    Iterable, 
    List, 
    Optional, 
    Tuple,
    TypeVar,
    Any
)
from typing_extensions import ParamSpec, Concatenate

if TYPE_CHECKING:
    from asyncpg import Connection

__all__: Tuple[str, ...] = (
    'ProfanityChecker',
)

T = TypeVar('T')
P = ParamSpec('P')


class ProfanityChecker(Generic[P, T]):
    """
    A class used to check if a string contains profanity.
    """
    
    permeate_mapping: ClassVar[Dict[str, List[str]]] = {
        'a': ['@'],
        'i': ['!', 'l', '1'],
        'd': ['b'],
        't': ['7'],
        'o': ['0'],
        's': ['$'],
        'y': ['i', 'ie']
    }  
    
    invalid_regex: ClassVar[Tuple[str, ...]] = (
        '.',
        '^',
        '$',
        '.'
    )
    
    def __init__(
        self, 
        *, 
        wrap: Callable[Concatenate[Callable[P, T], P], Awaitable[T]], 
        safe_connection: Callable[[], AsyncContextManager[Connection]]
    ) -> None:
        self.wrap: Callable[Concatenate[Callable[P, T], P], Awaitable[T]] = wrap
        self.safe_connection: Callable[[], AsyncContextManager[Connection]] = safe_connection
        
        self._profanity_regex: Optional[re.Pattern] = None
        self._database_profanity: Optional[List[str]] = None
    
    def __call__(self, blocking: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
        return self.wrap(blocking, *args, **kwargs)
    
    async def _raw_profanity(self) -> List[str]:
        async with self.safe_connection() as connection:
            data = await connection.fetch('SELECT word FROM profanity')
        
        self._database_profanity = profanity = [entry['word'] for entry in data]
        return profanity
    
    async def _permeate(self, words: List[str], /) -> List[str]:
        words = words.copy()
        
        for word in words:
            if word.endswith('er'): 
                words.append(word.replace('er', 'a')) 
                
            for index, char in enumerate(word):
                current = self.permeate_mapping.get(char.lower())
                if not current:
                    continue
                
                for switch in current:
                    formatted = word[0:index] + switch + word[index+1:]
                    words.append(formatted) # type: ignore
                    
                break 
            
        plural = [self(inflection.pluralize, word) for word in words] # type: ignore
        words.extend(await asyncio.gather(*plural))
        
        for word in words:
            for invalid in self.invalid_regex:
                word = word.replace(invalid, r'\{0}'.format(invalid))
        
        words = list(set(words)) # Clean duplicates
        words.sort(key=len)
        words.reverse()
        
        return words
    
    async def _build_regex(self) -> re.Pattern:
        words = await self._raw_profanity()
        extended = await self._permeate(words)
        return re.compile('|'.join(extended), flags=re.IGNORECASE)
    
    def _subber(self, match: re.Match) -> str:
        return '*' * len(match.group(0))
    
    async def censor(self, text: str) -> str:
        """|coro|
        
        A coroutine to censor profanity from a string.
        
        Parameters
        ----------
        text: :class:`str`
            The string to censor.
        
        Returns
        -------
        :class:`str`
            The censored string.
        """
        if not self._profanity_regex:
            self._profanity_regex = await self._build_regex()
        
        return self._profanity_regex.sub(self._subber, text)
