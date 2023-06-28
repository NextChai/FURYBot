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

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .panel import Panel as PanelType

# Mapping of Panel qualnames to Panel objects. This has been marked as a global variable
# because it's used to easily keep track of components registered at runtime. Additionally,
# this prevents the cls of a Panel holindg a reference to the Panel itself, which would
# be heavy on memory.
ALL_PANELS: Dict[str, PanelType[Any]] = {}


def remove_panel(cls_qualname: str) -> Optional[Panel[Any]]:
    return ALL_PANELS.pop(cls_qualname, None)


def get_panel(cls_qualname: str) -> Optional[PanelType[Any]]:
    return ALL_PANELS.get(cls_qualname, None)


from .decorators import *
from .field import *
from .panel import *
from .types import *
