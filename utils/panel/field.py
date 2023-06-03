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

from typing import TYPE_CHECKING, Any, Dict, Generic

from .types import T

if TYPE_CHECKING:
    from .types import FieldType
    from .panel import Panel


class Field(Generic[T]):
    """Represents a Field on a given panel. Depending on the type of the field,
    one of a couple things can happen.

    - If the field is a SUBITEM, then the field will be a button that points to a new panel.
    - If the field is a MODAL, then the field will be a button that opens a modal.
    - If the field is a select, then the field will be a dropdown menu.
    """

    if TYPE_CHECKING:
        panel: Panel[T]

    def __init__(self, name: str, type: FieldType, **kwargs: Any) -> None:
        self.name: str = name
        self.type: FieldType = type

        self._button_kwargs: Dict[str, Any] = {}
        for name in kwargs.keys():
            if name.startswith('button_'):
                self._button_kwargs[name[7:]] = kwargs.pop(name)
