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

from typing import TYPE_CHECKING, Optional, Type, Callable, Dict
from typing_extensions import dataclass_transform

from . import ALL_PANELS
from .types import FieldType, T
from .dataclass import create_dataclass
from .field import Field
from .panel import Panel


if TYPE_CHECKING:
    from discord import Embed


def register_panel(
    cls: Type[T],
    table_name: str,
    init: bool = True,
    repr: bool = True,
    slots: bool = True,
    create_embed: Optional[Callable[[Panel[T]], Embed]] = None,
    **fields: FieldType,
) -> Type[T]:
    """A helper function to register a given panel at runtime. This will insert the given
    panel into the global registry, and allow it to be used in the panel system.

    A majority of the time, though, you should be using `@register` instead of this.
    """
    if ALL_PANELS.get(cls.__qualname__) is not None:
        raise ValueError(f'Panel {cls.__qualname__} is already registered as a panel.')

    # We need to register this as a dataclass.
    cls = create_dataclass(cls, init=init, repr=repr, slots=slots)
    cls_fields = getattr(cls, '__dataclass_fields__')

    # We need to go through and ensure all the children and ensure that if a panel
    # child is a panel, it has the correct regristration.
    transformed_fields: Dict[str, Field[T]] = {}
    for field_name, field_type in fields.items():
        if field_name not in cls_fields:
            raise ValueError(f'Child {field_name} is not a valid field.')

        if field_type == FieldType.SUBITEM:
            sub_item = field_type.sub_item
            if ALL_PANELS.get(sub_item.__qualname__) is None:
                raise ValueError(
                    f'Child {field_name} is not a valid panel. You must register the panel first before you can add it as a child.'
                )

        transformed_fields[field_name] = Field(field_name, field_type)

    panel = Panel(cls, table_name, transformed_fields, create_embed=create_embed)

    for field in transformed_fields.values():
        field.panel = panel

    ALL_PANELS[cls.__qualname__] = panel

    return cls


@dataclass_transform()
def register(
    table_name: str,
    *,
    init: bool = True,
    repr: bool = True,
    slots: bool = True,
    create_embed: Optional[Callable[[Panel[T]], Embed]] = None,
    **fields: FieldType,
) -> Callable[[Type[T]], Type[T]]:
    def wrapped(cls: Type[T]) -> Type[T]:
        return register_panel(cls, table_name, init=init, repr=repr, slots=slots, create_embed=create_embed, **fields)

    return wrapped


def remove_panel(cls: Type[T]) -> Optional[Panel[T]]:
    return ALL_PANELS.pop(cls.__qualname__, None)
