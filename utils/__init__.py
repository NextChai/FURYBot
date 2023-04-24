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
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Iterable, List, Optional, Tuple, TypeVar

import discord

from .bases import *
from .cog import *
from .constants import *
from .context import *
from .error_handler import *
from .errors import *
from .images import *
from .link import *
from .profanity import *
from .query import *
from .time import *
from .timers import *
from .types import *
from .ui import *

if TYPE_CHECKING:
    import datetime

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


def parse_initial_extensions(extensions: Iterable[str]) -> Iterable[str]:
    if RUNNING_DEVELOPMENT:
        # When running development, the user can prefix extensions they'd like to ignore loading
        # using the `.env` file. So to allow a user to ignore something, they can do: `IGNORE_EXTENSIONS=ext1,ext2`
        if USE_CUSTOM_INITIAL_EXTENSIONS:
            extensions = INITIAL_EXTENSIONS

        return tuple(ext for ext in extensions if ext not in IGNORE_EXTENSIONS)

    return extensions


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


def human_timestamp(dt: datetime.datetime) -> str:
    return f'{discord.utils.format_dt(dt, "F")} ({discord.utils.format_dt(dt, "R")})'


def human_join(
    iterable: Iterable[Any], /, *, last: str = 'and', delimiter: str = ',', additional: Optional[str] = None
) -> str:
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

    finished: str
    if len(items) == 0:
        finished = ''
    elif len(items) == 1:
        finished = items[0]
    elif len(items) == 2:
        finished = f'{items[0]} {last} {items[1]}'
    else:
        finished = f'{delimiter.join(items[:-1])}, {last} {items[-1]}'

    if additional:
        finished += f' {additional}'

    return finished.strip()
