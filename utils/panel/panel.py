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

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Generic, Mapping, Optional, Type

from typing_extensions import Self

from .types import T
from .underlying import UnderlyingPanelView

if TYPE_CHECKING:
    from discord import Embed, Interaction

    from bot import FuryBot

    from .field import Field


class Panel(Generic[T]):
    _edit_coroutine: Optional[Callable[..., Coroutine[Any, Any, None]]] = None

    def __init__(self, cls: Type[T], table_name: str, name: str, fields: Mapping[str, Field[T]], **kwargs: Any) -> None:
        self.cls: Type[T] = cls

        self.table_name: str = table_name
        self.name: str = name
        self.fields: Mapping[str, Field[T]] = fields

        self._create_embed_func: Optional[Callable[[Self, T], Embed]] = kwargs.get('create_embed', None)

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        return self.cls(*args, **kwargs)

    def create_underlying_view(
        self, instance: T, target: Interaction[FuryBot], *, timeout: float = 120.0
    ) -> UnderlyingPanelView[T]:
        return UnderlyingPanelView(self, instance, timeout=timeout, parent=None, target=target)

    def create_embed(self, embed_cls: Callable[..., Embed]) -> Embed:
        # An embed for a given panel can be shown in one of two ways. For each field in the panel,
        # it will have a corresponding embed field. If the field is a sub item, it will show a miniature
        # embed of the sub item.
        embed = embed_cls(title=f'Manage {self.name}', description='Use the buttons below to manage this panel.')

        # for field in fields:
        #   ...

        return embed
