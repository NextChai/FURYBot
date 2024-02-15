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

import aiofile
import re
import random
from typing import Optional, Any, List
from typing_extensions import Self


PUNCTUATION_REGEX = re.compile(r'[!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~]')


class SentenceGrabber:
    def __init__(
        self,
        content: Optional[List[str]] = None,
        filename: Optional[str] = None,
        min_sentence_length: int = 5,
        max_sentence_length: int = 50,
    ) -> None:
        assert content or filename, 'You must provide either content or a filename.'

        self.content: Optional[List[str]] = content
        self.filename: Optional[str] = filename
        self.min_sentence_length: int = min_sentence_length
        self.max_sentence_length: int = max_sentence_length
        self.__index: int = -1

    async def __aenter__(self) -> Self:
        if self.filename:
            # Open this file and grab its contents (aiofile)
            async with aiofile.async_open(self.filename, mode='r', encoding="utf-8") as f:
                content = await f.read()

            # Split the content by period, strip it, and remove empty strings
            cleaned_content: List[str] = []
            for sentence in content.split('.'):
                sentence = sentence.strip()
                if sentence:
                    # Ensure it is within the bounds of the min and max sentence length
                    total_words = len(sentence.split())
                    if total_words > self.min_sentence_length and total_words < self.max_sentence_length:
                        cleaned_content.append(sentence)

            if not cleaned_content:
                raise ValueError('The file provided did not contain any valid sentences.')

            random.shuffle(cleaned_content)
            self.content = cleaned_content
        elif self.content:
            random.shuffle(self.content)

            # Ensure each sentence in the content does not exceed the max sentence length (or min)
            self.content = [
                sentence
                for sentence in self.content
                if len(sentence) > self.min_sentence_length and len(sentence) < self.max_sentence_length
            ]

        return self

    async def __aexit__(self, *args: Any) -> None: ...

    def __iter__(self):
        return self

    def __next__(self):
        return self.grab()

    def grab(self) -> str:
        assert self.content, 'You must provide content or use the class as a context manager with a file.'

        self.__index += 1
        if self.__index >= len(self.content):
            raise StopIteration

        sentence = self.content[self.__index]

        # Remove all puntuations and strip the sentence
        sentence = PUNCTUATION_REGEX.sub('', sentence).strip()

        # Ensure that if there's any new lines, we replace them with a space
        sentence = sentence.replace('\n', ' ')

        # Capitalize the first char and ensure it has a period at the end
        if not sentence[0].isupper():
            sentence = sentence.capitalize()

        if sentence[-1] != '.':
            sentence += '.'

        return sentence
