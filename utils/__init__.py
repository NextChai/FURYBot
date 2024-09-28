"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to 
non-commercial purposes. Distribution, sublicensing, and sharing of this file 
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not 
misrepresent the original material. This license does not grant any 
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Iterable, List, Optional, Tuple, TypeVar

import discord

from .bases import *
from .cog import *
from .context import *
from .error_handler import *
from .errors import *
from .images import *
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

INITIAL_EXTENSIONS: List[str] = [e.strip() for e in os.environ.get('INITIAL_EXTENSIONS', '').split(',')]
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


def make_table(rows: List[List[Any]], labels: Optional[List[str]] = None, centered: bool = False) -> str:
    if labels is None:
        labels = []

    # Compute the column widths.
    col_widths: List[int] = []
    for i, col in enumerate(zip(*rows)):
        label_width = len(labels[i]) if i < len(labels) else 0
        col_widths.append(max(len(str(cell)) for cell in col) + 2)  # Add 2 for padding
        col_widths[-1] = max(col_widths[-1], label_width + 2) if labels else col_widths[-1]

    # Construct the top border.
    top_border = "┌" + "┬".join("─" * width for width in col_widths) + "┐\n"

    # Construct the header row.
    if labels:
        header_row = "│" + "│".join(f" {str(label).center(width - 2)} " for label, width in zip(labels, col_widths)) + "│\n"
        middle_border = "├" + "┼".join("─" * width for width in col_widths) + "┤\n"
    else:
        header_row = ""
        middle_border = ""

    # Construct the data rows.
    data_rows: List[str] = []
    for row in rows:
        data_row = (
            "│"
            + "│".join(
                f" {str(cell).center(width - 2)} " if centered else f" {str(cell).ljust(width - 2)} "
                for cell, width in zip(row, col_widths)
            )
            + "│\n"
        )
        data_rows.append(data_row)

    # Construct the bottom border.
    bottom_border = "└" + "┴".join("─" * width for width in col_widths) + "┘"

    # Combine the components into the final table string.
    table = top_border + header_row + middle_border + "".join(data_rows) + bottom_border

    return table
