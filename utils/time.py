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

import datetime
import re
from typing import TYPE_CHECKING, Any, Optional, Tuple, Type, TypeVar

import discord
import parsedatetime
import pytz
from dateutil.relativedelta import relativedelta
from discord import app_commands
from typing_extensions import Self

from .errors import BadArgument

if TYPE_CHECKING:
    from bot import FuryBot

# Monkey patch mins and secs into the units
units: Any = parsedatetime.pdtLocales['en_US'].units
units['minutes'].append('mins')
units['seconds'].append('secs')

STT = TypeVar('STT', bound='ShortTime')
HTT = TypeVar('HTT', bound='HumanTime')
TT = TypeVar('TT', bound='Time')

__all__: Tuple[str, ...] = ('ShortTime', 'HumanTime', 'Time', 'TimeTransformer', 'human_timedelta')


intervals = (
    ('week', 60 * 60 * 24 * 7),
    ('day', 60 * 60 * 24),
    ('hour', 60 * 60),
    ('minute', 60),
    ('second', 1),
)


def human_timedelta(seconds: float) -> str:
    """
    Turns seconds into human readable time.
    """
    if seconds == 0:
        return 'No time.'

    message = ''

    for name, amount in intervals:
        n, seconds = divmod(seconds, amount)

        if n == 0:
            continue

        message += f'{n} {name + "s" * (n != 1)} '

    return message.strip()


class ShortTime:
    """Represents a shortimte transformer. This will use parsedatetime alongside a compiled
    regex to format time. Such as `1d 6h`, etc.

    Parameters
    ----------
    argument: :class:`str`
        The argument to convert.
    now: Optional[:class:`datetime.datetime`]
        The current time. Defaults to :class:`datetime.datetime.now`.
    """

    __slots__: Tuple[str, ...] = ('dt',)

    compiled = re.compile(
        r"""
        (?:(?P<years>[0-9])(?:\s)?(?:years?|y))?             
        (?:(?P<months>[0-9]{1,2})(?:\s)?(?:months?|mo))?     
        (?:(?P<weeks>[0-9]{1,4})(?:\s)?(?:weeks?|w))?        
        (?:(?P<days>[0-9]{1,5})(?:\s)?(?:days?|d))?          
        (?:(?P<hours>[0-9]{1,5})(?:\s)?(?:hours?|h))?        
        (?:(?P<minutes>[0-9]{1,5})(?:\s)?(?:minutes?|m))?    
        (?:(?P<seconds>[0-9]{1,5})(?:\s)?(?:seconds?|s))?    
        """,
        re.VERBOSE,
    )

    def __init__(self, argument: str) -> None:
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise BadArgument('invalid time provided')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = datetime.datetime.now(pytz.timezone('US/Eastern'))

        dt = now + relativedelta(**data)  # type: ignore
        self.dt = dt.replace(tzinfo=datetime.timezone.utc)

    @classmethod
    async def convert(cls: Type[STT], interaction: discord.Interaction[FuryBot], argument: str) -> STT:
        """|coro|

        A method used to transform the given argument to a :class:`ShortTime` object.

        Parameters
        ----------
        ctx: :class:`Context`
            The context of the command.
        argument: :class:`str`
            The argument to transform.

        Returns
        -------
        :class:`ShortTime`
            The transformed argument.
        """
        return cls(argument)


class HumanTime:
    """Represents a human readable time transformer. This will use parsedatetime to attempt
    and transform given input to a :class:`datetime.datetime` object.

    Parameters
    ----------
    argument: :class:`str`
        The argument to transform.
    now: Optional[:class:`datetime.datetime`]
        The current time. Defaults to :class:`datetime.datetime.now`.

    Attributes
    ----------
    dt: :class:`datetime.datetime`
        The datetime object that was created from the argument.
    """

    __slots__: Tuple[str, ...] = ('dt', '_past')

    calendar: Any = parsedatetime.Calendar(version=parsedatetime.VERSION_CONTEXT_STYLE)

    def __init__(self, argument: str, *, now: Optional[datetime.datetime] = None) -> None:
        now = now or datetime.datetime.now(datetime.timezone.utc)
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise BadArgument('invalid time provided, try e.g. "tomorrow" or "3 days"', tzinfo=pytz.timezone('US/Eastern'))

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt: datetime.datetime = dt.replace(tzinfo=datetime.timezone.utc)
        self._past = dt < now

    @classmethod
    async def transform(cls: Type[HTT], interaction: discord.Interaction[FuryBot], argument: str) -> HTT:
        """|coro|

        A method used to convert the given argument to a :class:`HumanTime` object.

        Parameters
        ----------
        ctx: :class:`Context`
            The context of the command.
        argument: :class:`str`
            The argument to convert.

        Returns
        -------
        :class:`HumanTime`
            The converted argument.
        """
        return cls(argument, now=interaction.created_at)


class Time(HumanTime):
    """Represents a base time transformer. This transformer will try and convert
    using :class:`ShortTime` and fallback to :class:`HumanTime` if it fails.

    This inherits :class:`HumanTime`.

    Parameters
    ----------
    argument: :class:`str`
        The argument to convert.
    now: Optional[:class:`datetime.datetime`]
        The current time. Defaults to :class:`datetime.datetime.now`.

    Attributes
    ----------
    dt: :class:`datetime.datetime`
        The datetime object that was created from the argument.
    """

    __slots__: Tuple[str, ...] = ()

    def __init__(self, argument: str, *, now: Optional[datetime.datetime] = None) -> None:
        try:
            o = ShortTime(argument)
        except Exception:
            super().__init__(argument, now=now)
        else:
            self.dt: datetime.datetime = o.dt
            self._past = False


class TimeTransformer(app_commands.Transformer):
    """Represents a user friendly time transformer.

    Attributes
    ----------
    default: Optional[:class:`str`]
        An optional default value to use if the argument is not provided.
    dt: Optional[:class:`datetime.datetime`]
        The datetime object that was created from the argument.
    arg: Optional[:class:`str`]
        The argument that was provided.

    """

    __slots__: Tuple[str, ...] = (
        'converter',
        'dt',
        'arg',
        'default',
    )

    def __init__(
        self,
        default: Optional[str] = None,
    ) -> None:
        self.dt: Optional[datetime.datetime] = None
        self.arg: Optional[str] = None
        self.default: Optional[str] = default

    async def _check_constraints(self, now: datetime.datetime, remaining: str) -> Self:
        """|coro|

        A coroutine to ensure that the given inputs are not in the past or missing arguments.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction of the command.
        now: :class:`datetime.datetime`
            The current time.
        remaining: :class:`str`
            The remaining arguments.
        """
        assert self.dt is not None

        if self.dt < now:
            raise BadArgument('This time is in the past.')

        if not remaining and not self.default:
            raise BadArgument('Missing argument after the time.')

        self.arg = remaining or self.default
        return self

    async def transform(self, interaction: discord.Interaction[FuryBot], value: Any) -> Self:
        """|coro|

        Transform the user\'s argument into a :class:`TimeTransformer` object.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction of the command.
        value: Any
            The value to transform.

        Returns
        -------
        :class:`TimeTransformer`
            The transformed value.
        """
        result = self.__class__(default=self.default)

        calendar = HumanTime.calendar
        regex = ShortTime.compiled

        now = interaction.created_at

        match = regex.match(value)
        if match is not None and match.group(0):
            data = {k: int(v) for k, v in match.groupdict(default=0).items()}
            remaining = value[match.end() :].strip()
            result.dt = now + relativedelta(**data)  # type: ignore
            return await result._check_constraints(now, remaining)

        if value.endswith('from now'):
            value = value[:-8].strip()

        if value[0:2] == 'me':
            # starts with "me to", "me in", or "me at "
            if value[0:6] in ('me to ', 'me in ', 'me at '):
                value = value[6:]

        elements = calendar.nlp(value, sourceTime=now)
        if elements is None or len(elements) == 0:
            raise BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

        dt, status, begin, end, _ = elements[0]

        if not status.hasDateOrTime:
            raise BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

        if begin not in (0, 1) and end != len(value):
            raise BadArgument('I\'m so sorry but I didn\'t understand this time!')

        if not status.hasTime:
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        if status.accuracy == parsedatetime.pdtContext.ACU_HALFDAY:
            dt = dt.replace(day=now.day + 1)

        result.dt = dt.replace(tzinfo=datetime.timezone.utc)

        if begin in (0, 1):
            if begin == 1:
                if value[0] != '"':
                    raise BadArgument('Expected quote before time input...')

                if not (end < len(value) and value[end] == '"'):
                    raise BadArgument('If the time is quoted, you must unquote it.')

                remaining = value[end + 1 :].lstrip(' ,.!')
            else:
                remaining = value[end:].lstrip(' ,.!')
        elif len(value) == end:
            remaining = value[:begin].strip()
        else:
            raise BadArgument('I\'m so sorry but I didn\'t understand this time!')

        return await result._check_constraints(now, remaining)
