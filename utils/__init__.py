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

import os
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Iterable, Tuple, TypeVar, List

from .bases import *
from .cog import *
from .constants import *
from .context import *
from .error_handler import *
from .errors import *
from .link import *
from .query import *
from .time import *
from .timers import *
from .types import *
from .ui_kit import *

if TYPE_CHECKING:
    import discord

    BV = TypeVar('BV', bound='discord.ui.View')
    ButtonCallback = Callable[[BV, discord.Interaction[Any], discord.ui.Button[BV]], Coroutine[Any, Any, Any]]

__all__: Tuple[str, ...] = ('RUNNING_DEVELOPMENT', 'default_button_doc_string', 'human_join')


def _parse_environ_boolean(key: str, *, false_if_none: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        if false_if_none:
            return False

        return True

    return val.lower() in ("true", "1")


RUNNING_DEVELOPMENT: bool = _parse_environ_boolean('RUN_DEVELOPMENT')
BYPASS_SETUP_HOOK: bool = _parse_environ_boolean('BYPASS_SETUP_HOOK', false_if_none=True)
BYPASS_SETUP_HOOK_CACHE_LOADING: bool = _parse_environ_boolean('BYPASS_SETUP_HOOK_CACHE_LOADING', false_if_none=True)
USE_CUSTOM_INITIAL_EXTENSIONS: bool = _parse_environ_boolean('USE_CUSTOM_INITIAL_EXTENSIONS', false_if_none=True)

INITIAL_EXTENSIONS: List[str] = os.environ.get('INITIAL_EXTENSIONS', '').split(',')
IGNORE_EXTENSIONS: List[str] = os.environ.get('IGNORE_EXTENSIONS', '').split(',')

START_TIMER_MANAGER: bool = _parse_environ_boolean(
    'START_TIMER_MANAGER',
)


def default_button_doc_string(func: ButtonCallback[BV]) -> ButtonCallback[BV]:
    default_doc = """
    |coro|
    
    {doc}
    
    Parameters
    ----------
    interaction: :class:`discord.Interaction`
        The interaction that triggered this button.
    button: :class:`discord.ui.Button`
        The button that was clicked.
    """
    func.__doc__ = default_doc.format(doc=func.__doc__ or '')
    return func


def human_join(iterable: Iterable[Any], /, *, last: str = 'and', delimiter: str = ',') -> str:
    """Joins an iterable of strings into a human readable string.

    Parameters
    ----------
    iterable: Iterable[:class:`str`]
        The iterable of strings to join.
    last: :class:`str`
        The word to use to join the last two items.
    delimiter: :class:`str`
        The delimiter to use to join all other items.

    Returns
    -------
    :class:`str`
        The human readable string.
    """
    items = list(iterable)
    if len(items) == 0:
        return ''
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f'{items[0]} {last} {items[1]}'
    else:
        return f'{delimiter.join(items[:-1])}, {last} {items[-1]}'
