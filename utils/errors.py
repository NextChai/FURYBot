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

from typing import Tuple

import discord

__all__: Tuple[str, ...] = ('FuryException', 'ProfanityFailure', 'MemberAlreadyLocked', 'MemberNotLocked')


class FuryException(discord.ClientException):
    """The base Fury Exception for all custom Fury bot excpetions."""

    pass


class ProfanityFailure(FuryException):
    """The exception raised when a profanity filter fails."""

    pass


class MemberAlreadyLocked(FuryException):
    """Raised when a member is already locked."""

    pass


class MemberNotLocked(FuryException):
    """Raised when a member is not locked."""

    pass


class TimerNotFound(FuryException):
    """
    An exception raised when a timer is not found.

    Attributes
    ----------
    id: :class:`int`
        The ID of the timer.
    """

    __slots__: Tuple[str, ...] = ('id',)

    def __init__(self, id: int) -> None:
        super().__init__(f'Timer {id} was not found!')
        self.id: int = id
