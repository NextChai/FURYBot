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

from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from .panel import Panel as PanelType

# Mapping of Panel qualnames to Panel objects. This has been marked as a global variable
# because it's used to easily keep track of components registered at runtime. Additionally,
# this prevents the cls of a Panel holindg a reference to the Panel itself, which would
# be heavy on memory.
ALL_PANELS: Dict[str, PanelType[Any]] = {}

from .panel import *
from .dataclass import *
from .decorators import *
from .field import *
from .types import *

"""
The goal of the panel creator is to allow the bulk
editing of items within a set of classes to be edited by dynamic
views by a given user.

Let's walk through an example of this.

.. code-block :: python3

    @panel.register(
        'busses.persons', # The name of the table that represents this item
        name=panel.type.MODAL, # *how* the user will edit the "age" field on the person
        age=panel.type.MODAL, # *how* the user will edit the "name" field on the person
    )
    class Person:
        id: int
        name: str
        age: int

    @panel.register(
        'busses.settings',
        color=panel.type.MODAL, # *how* the user will edit the "color" field on the bus
        people=panel.type.SUBTABLE('busses.persons') # Points to the table that represents the "people" field. This is a subtable within the view.
    )
    class Bus:
        id: int
        color: str
        people: List[Person]

The goal of this is to allow the user to create a dynamic view that allows them to edit the "color" of the bus,
and the "name" and "age" of **each** person in the bus.

Let's look at a more Discord specific example:

.. code-block:: python3

    @panel.register(
        'settings.setting',
        channel=panel.type.TEXT_CHANNEL_SELECT,
        role=panel.type.ROLE_SELECT,
        user=panel.type.USER_SELECT,
        when=panel.type.DATETIME_MODAL
    )
    class Setting:
        id: int
        channel: discord.TextChannel
        role: discord.Role,
        user: discord.User
        when: datetime.datetime

    @panel.register('settings.holder', settings=panel.type.SUBTABLE('settings')
    class SettingHolder:
        id: int
        settings: List[Setting]

This entire system will work on the premise that the user will be able to edit the "channel", "role", "user", and "when".
"""
