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

from typing import ClassVar, List
from functools import cached_property


class Row:
    """Used to represent a Row to a database.
    
    Attributes
    ----------
    name: :class:`str`
        The key's name.
    value: :class:`str`
        The key's value.
    """
    __slots__ = ('name', 'value', '_original_args')
    
    def __init__(self, name: str, type: str, *args) -> None:
        self.name = name
        self.value = type
        self._original_args = args # EXAMPLE:: PRIMARY KEY NOT NULL
        
    def __str__(self) -> str:
        return f'{self.name} {self.value} {" ".join(self._original_args)}'
    
    def __repr__(self) -> str:
        return f'<Row :: name: {self.name}:: value: {self.value}>'
    
    
class TableMeta(type):
    __table_name__: str
    
    def __new__(cls, *args, **kwargs):
        name, bases, attrs = args
        attrs['__table_name__'] = kwargs.pop('name', name)
        
        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        return new_cls

    @classmethod
    def qualified_name(cls) -> str:
        return cls.__table_name__


class Table(metaclass=TableMeta):
    __table_name__: ClassVar[str]
    
    def __init__(self, *, keys: List[Row]) -> None:
        self.keys: List[Row] = keys

    @cached_property
    def qualified_name(self) -> str:
        return self.__table_name__
        
    @cached_property
    def create_string(self) -> str:
        """:class:`str`: Returns a string that can be used to create the table."""
        return 'CREATE TABLE IF NOT EXISTS {0} ({1});'.format(
            self.qualified_name,
            ', '.join([str(key) for key in self.keys])
        )
        
    async def create(self, connection) -> None:
        """Creates the table."""
        await connection.execute(self.create_string)

