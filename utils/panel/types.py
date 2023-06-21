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

import inspect
from typing import TYPE_CHECKING, Any, Callable, Concatenate, Generic, Iterable, Optional, Type, TypeVar
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from discord import ChannelType

P = ParamSpec('P')
T = TypeVar('T')

MISSING: Any = type('MISSING', (object,), {})()


# A decorator that allows us to create a new panel field type one of a couple ways.
# PanelFieldType.MODAL -> A panel field type with value 1 << 0
# PanelFieldType.SUBTABLE('cock') -> A panel field that takes a parameter (not all of them do)
# PanelFiledType.SUBTABLE('penis') == PanelFieldType.SUBTABLE
# >>> True
class panel_field(Generic[P]):
    def __init__(self, func: Callable[Concatenate[FieldType, P], int]) -> None:
        self.func: Callable[Concatenate[FieldType, P], int] = func
        self.func_arg_count = len(inspect.signature(func).parameters)

    def __get__(self, instance: Optional[FieldType], owner: Type[FieldType]) -> Any:
        if instance is not None:
            # This is being called on an instance of the class, IE something like PanelFieldType(0).MODAL.
            # This means we don't need to do anything.
            return

        # We're being called on the class itself, IE PanelFieldType.MODAL.
        # We need to return a new instance of the class with the value set.
        mock_self = FieldType(0)
        value = self.func(mock_self, *([MISSING] * (self.func_arg_count - 1)))  # type: ignore

        # Inject the relevent values
        mock_self._value = value
        setattr(mock_self, '__overriden_call__', self.__call__)

        return mock_self

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Any:
        # We can create an empty instance of the class, and then call the function on it.
        mock_self = FieldType(0)

        value = self.func(mock_self, *args, **kwargs)
        mock_self._value = value

        return mock_self


class FieldType:
    def __init__(self, value: int) -> None:
        self._value: int = value

        self.sub_item: Type[Any] = MISSING
        self.channel_types: Iterable[ChannelType] = MISSING

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, self.__class__) and self._value == __value._value

    def __ne__(self, __value: object) -> bool:
        return not self.__eq__(__value)

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f'<PanelFieldType value={self._value}>'

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        call_func = self.__dict__.get('__overriden_call__')
        if call_func is not None:
            return call_func(*args, **kwargs)

        raise TypeError(f'PanelFieldType {self.__class__.__name__} is not callable.')

    @panel_field
    def SUBITEM(self, item: Type[Any] = MISSING) -> int:
        self.sub_item = item
        return 1 << 0

    @panel_field
    def BOOLEAN_MODAL(self) -> int:
        return 1 << 1

    @panel_field
    def DATETIME_MODAL(self) -> int:
        return 1 << 2

    @panel_field
    def TIMEDELTA_MODAL(self) -> int:
        return 1 << 9

    @panel_field
    def INTEGER_MODAL(self) -> int:
        return 1 << 3

    @panel_field
    def FLOAT_MODAL(self) -> int:
        return 1 << 4

    @panel_field
    def CHANNEL_SELECT(self, channel_types: Iterable[ChannelType] = MISSING) -> int:
        self.channel_types = channel_types
        return 1 << 5

    @panel_field
    def ROLE_SELECT(self) -> int:
        return 1 << 6

    @panel_field
    def USER_SELECT(self) -> int:
        return 1 << 7

    @panel_field
    def TEXT_MODAL(self) -> int:
        return 1 << 8
