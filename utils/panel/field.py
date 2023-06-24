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

from types import NoneType
from typing import TYPE_CHECKING, Any, Callable, Dict, Generic, Optional, Union
from typing_extensions import Self

from .types import MISSING, T

if TYPE_CHECKING:
    from .panel import Panel
    from .types import FieldType


class Field(Generic[T]):
    if TYPE_CHECKING:
        panel: Panel[T]

    def __init__(
        self,
        type: FieldType = MISSING,
        name: str = MISSING,
        annotation: Any = MISSING,
        default: Any = MISSING,
        converter: Optional[Callable[[Any], Any]] = None,
        ignored: bool = MISSING,
        display_name: Optional[str] = None,
        embed_field_func: Optional[Callable[[Self, Any], Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> None:
        self.name: str = name
        self.type: FieldType = type

        self.annotation: Any = annotation
        self.default: Any = default
        self.converter: Optional[Callable[[Any], Any]] = converter
        self.display_name = display_name or self.name
        self.embed_field_func: Optional[Callable[[Self, Any], Dict[str, Any]]] = embed_field_func

        self._ignored: bool = ignored

    def __repr__(self) -> str:
        return (
            f'<Field name={self.name!r} annotation={self.annotation!r} default={self.default!r} '
            f'converter={bool(self.converter)} ignored={self.ignored} type={self.type!r}>'
        )

    @property
    def ignored(self) -> bool:
        if self._ignored is MISSING:
            return self.name.startswith('_')

        return self._ignored

    @ignored.setter
    def ignored(self, value: bool) -> None:
        self._ignored = value

    def transform(self, value: Optional[Any]) -> Any:
        if value is None:
            # We can't do anything if the default *is* missing, so value
            # will have to stay as None
            if self.default is not MISSING:
                value = self.default

        if self.converter is not None:
            value = self.converter(value)

        return value

    def create_embed_field(self, value: Any) -> Dict[str, Any]:
        if self.embed_field_func is not None:
            return self.embed_field_func(self, value)

        raise NotImplementedError('No embed field function was provided for this field')


def field(
    *,
    type: FieldType = MISSING,
    name: Optional[str] = None,
    display_name: Optional[str] = None,
    annotation: Any = MISSING,
    default: Any = MISSING,
    converter: Optional[Callable[[Any], Any]] = None,
    ignored: bool = MISSING,
    embed_field_func: Optional[Callable[[Field[Any], Any], Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Any:
    # The field class doesn't take the same types of arguments as the decorator,
    # so we need to do some work to make sure we can handle both.
    data: Dict[str, Any] = {
        'default': default,
        'converter': converter,
        'ignored': ignored,
        'type': type,
        'display_name': display_name,
        'embed_field_func': embed_field_func,
    }

    if name is not None:
        data['name'] = name

    if annotation is not MISSING:
        data['annotation'] = annotation

        if default is MISSING:
            # We can check if the annotation is Optional. If it is the default
            # here can be None.
            origin = getattr(annotation, '__origin__', None)
            if origin is not None and origin is Union:
                args = origin.__args__
                if args.index(NoneType) == len(args) - 1:
                    data['default'] = None

    return Field(**data, **kwargs)
