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

import dataclasses
import datetime
from typing import Optional, Tuple, Type, Any, Union, List
from typing_extensions import Self
import re
from dateutil.relativedelta import relativedelta
import parsedatetime

import discord
from discord import app_commands

from .errors import BadArgument

__all__: Tuple[str, ...] = ('ShortTime', 'HumanTime', 'TransformedTime', 'TimeTransformer')

EST_OFFSET = datetime.timedelta(hours=4)


def _clamp_est(dt: datetime.datetime) -> datetime.datetime:
    # Clamps UTC to EST time by subtracting 4 hours
    return dt - EST_OFFSET


class ShortTime:
    """Represents a shortimte transformer. This will use parsedatetime alongside a compiled
    regex to format time. Such as `1d 6h`, etc.

    Please note you shouldn't create an instance of this class, use :meth:`from_argument` instead.

    Attributes
    ----------
    argument: :class:`str`
        The argument to convert.
    dt: :class:`datetime.datetime`
        The transformed datetime object.
    remaining: :class:`str`
        The remaining string after parsing.
    """

    __slots__: Tuple[str, ...] = ('argument', 'dt', 'remaining', '_now')

    compiled = re.compile(
        """(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """,
        re.VERBOSE,
    )

    def __init__(
        self, argument: str, dt: datetime.datetime, /, *, now: datetime.datetime, remaining: Optional[str] = None
    ) -> None:
        self.argument: str = argument
        self.dt: datetime.datetime = dt
        self.remaining: Optional[str] = remaining
        self._now: datetime.datetime = now

    @classmethod
    def from_argument(
        cls: Type[Self], argument: str, /, *, now: Optional[datetime.datetime] = None, default: Optional[str] = None
    ) -> Self:
        """Transform the given argument into a :class:`ShortTime` object.

        Parameters
        ----------
        argument: :class:`str`
            The argument to convert.
        now: Optional[:class:`datetime.datetime`]
            The datetime to use as the base. Defaults to :func:`datetime.datetime.utcnow`.
        default: Optional[:class:`str`]
            The default time to use if the argument is empty.
        """
        match = cls.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise BadArgument('invalid time provided')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        remaining = argument[match.end() :].strip()

        now = now or datetime.datetime.utcnow()
        dt = _clamp_est(now + relativedelta(**data))

        return cls(argument, dt, now=now, remaining=remaining or default)

    @property
    def is_past(self) -> bool:
        """:class:`bool`: Whether the time is in the past."""
        return self.dt < self._now


class HumanTime:
    """Represents a human time transformer. This will parse human given strings
    to datetime objects using parsedatetime.

    Please note you shouldn't create an instance of this class, use :meth:`from_argument` instead.

    Attributes
    ----------
    argument: :class:`str`
        The argument that was converted.
    dt: :class:`datetime.datetime`
        The datetime object that was created.
    remaining: Optional[:class:`str`]
        The remaining string that was not parsed.
    """

    calendar: Any = parsedatetime.Calendar(version=2)  # 2 for VERSION_CONTEXT_STYLE

    def __init__(
        self, argument: str, dt: datetime.datetime, /, *, now: datetime.datetime, remaining: Optional[str] = None
    ) -> None:
        self.argument: str = argument
        self.dt: datetime.datetime = dt
        self.remaining: Optional[str] = remaining
        self._now: datetime.datetime = now

    @classmethod
    def from_argument(
        cls: Type[Self], argument: str, /, *, now: Optional[datetime.datetime] = None, default: Optional[str] = None
    ) -> Self:
        """Transform the given argument into a :class:`HumanTime` object.

        Parameters
        ----------
        argument: :class:`str`
            The argument to convert.
        now: Optional[:class:`datetime.datetime`]
            The datetime to use as the base. Defaults to :func:`datetime.datetime.utcnow`.
        default: Optional[:class:`str`]
            The default time to use if the argument is empty.
        """
        now = now or datetime.datetime.utcnow()
        elements = cls.calendar.nlp(argument, sourceTime=now)
        if elements is None or len(elements) == 0:
            raise BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

        dt, ctx, begin, end, _ = elements[0]

        if not ctx.hasDateOrTime:
            raise BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

        if begin not in (0, 1) and end != len(argument):
            raise BadArgument('I\'m so sorry but I didn\'t understand this time!')

        if not ctx.hasTime:
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        if ctx.accuracy == parsedatetime.pdtContext.ACU_HALFDAY:  # type: ignore
            dt = dt.replace(day=now.day + 1)

        dt = _clamp_est(dt)

        if begin in (0, 1):
            if begin == 0:
                remaining = argument[end + 1 :].lstrip(' ,.!')
            else:
                remaining = argument[end:].lstrip(' ,.!')
        elif len(argument) == end:
            remaining = argument[:begin].strip()
        else:
            raise BadArgument('I didn\'t understand this, try again!')

        return cls(argument, dt, now=now, remaining=remaining or default)

    @property
    def is_past(self) -> bool:
        """:class:`bool`: Whether the time is in the past."""
        return self.dt < self._now


@dataclasses.dataclass(init=True, repr=True)
class TransformedTime:
    """Represents the object returned when the :class:`TimeTransformer` class
    has transformed a given argument.

    Attributes
    ----------
    dt: :class:`datetime.datetime`
        The datetime object that was created.
    now: :class:`datetime.datetime`
        The current time, in utc format.
    arg: :class:`str`
        The remaining string that was not parsed. This could
        be the default depending on the transformer used.
    default: Optional[:class:`str`]
        The default arg to use if not provided.
    """

    dt: datetime.datetime
    now: datetime.datetime
    arg: str
    default: Optional[str]

    @property
    def is_unique_arg(self) -> bool:
        """:class:`bool`: Whether the :attr:`arg` was written by the user or not."""
        return self.arg != self.default


class TimeTransformer(app_commands.Transformer):
    """Represents a time transformer. This will parse human given strings
    into datetime objects using parsedatetime and regex depending on the
    user input.

    Parameters
    ----------
    default: Optional[:class:`str`]
        The default argument to add if the user does not provide one.
    past: :class:`bool`
        Whether to allow past times or not. This defaults to ``False``.
    """

    def __init__(self, default: Optional[str] = None, /, *, past: bool = False) -> None:
        self.default: Optional[str] = default
        self.past: bool = past
        self.past: bool = past

    async def _transform_time(self, transformed: Union[ShortTime, HumanTime]) -> TransformedTime:
        if not self.past and transformed.is_past:
            raise BadArgument('This time is in the past!')

        if not transformed.remaining:
            raise BadArgument('Expected remaining argument after time! For example, "5 minutes for washing dishes"')

        return TransformedTime(dt=transformed.dt, now=transformed._now, arg=transformed.remaining, default=self.default)

    async def autocomplete(self, interaction: discord.Interaction, value: str, /) -> List[app_commands.Choice[str]]:
        """|coro|

        Gives the user a blanket list of time choices to use.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from the autocomplete.
        value: :class:`str`
            The value of the argument.

        Returns
        -------
        List[:class:`discord.app_commands.Choice`]
            A list of choices to use.
        """
        default_choices = ['30 minutes', '1 hour', '12 hours', 'tomorrow', 'two days', '1 week']
        return [app_commands.Choice(name=choice.title(), value=choice) for choice in default_choices]

    async def transform(self, interaction: discord.Interaction, value: str, /) -> TransformedTime:
        """|coro|

        Transforms the given value to a :class:`TransformedTime` object.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from the command being invoked.
        value: :class:`str`
            The value of the argument.

        Returns
        -------
        :class:`TransformedTime`
            The transformed time object.

        Raises
        ------
        BadArgument
            The time provided was invalid.
        """
        try:
            transformed = ShortTime.from_argument(value, now=interaction.created_at, default=self.default)
        except BadArgument:
            pass
        else:
            return await self._transform_time(transformed)

        transformed = HumanTime.from_argument(value, now=interaction.created_at, default=self.default)
        return await self._transform_time(transformed)
