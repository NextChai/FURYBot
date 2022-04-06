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

import inspect
import uuid
from typing import (
    Any,
    Callable,
    Optional,
    Type, 
    TypeVar,
    TYPE_CHECKING
)

import discord
from discord.ext import commands

from .checks import *
from .constants import *
from .context import *
from .errors import *
from .profanity_filter import *
from .time import *

if TYPE_CHECKING:
    from bot import FuryBot
    import datetime

T = TypeVar('T')

def copy_doc(original: Callable[..., Any]) -> Callable[[T], T]:
    """Used to copy the documenation from one function to another.
    
    Parameters
    ----------
    original: Callable
        The original function to copy the documenation from.
    """
    def decorator(overriden: T) -> T:
        """Used to transfer the documentation from one function to another.
        
        Parameters
        ----------
        overridden: Callable   
            The function to copy the documentation to.
        """
        if overriden.__doc__:
            overriden.__doc__ = f'{overriden.__doc__}\n{original.__doc__}'
        else:
            overriden.__doc__ = original.__doc__
            
        overriden.__signature__ = inspect.signature(original)  # type: ignore
        return overriden

    return decorator

def _check_for_hierarchy(member: discord.Member) -> bool:
    guild = member.guild
    me = guild.me
    
    if member.top_role >= me.top_role:
        return False
    if member == me:
        return False
    if guild.owner == member:
        return False
    
    return True

def _format_dt(dt: datetime.datetime) -> str:
    try:
        return discord.utils.format_dt(dt, style='F')
    except OverflowError:
        return 'Time is too far in the future.'


class BaseCog(commands.Cog):
    """The base class for all cogs.
    
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot that this cog is attached to.
    """
    emoji: Optional[discord.PartialEmoji] = None
    brief: Optional[str] = None
    id: int = int(str(int(uuid.uuid4()))[:20])
    
    def __init_subclass__(cls: Type[BaseCog], **kwargs) -> None:
        cls.emoji = kwargs.pop('emoji', None)
        cls.brief = kwargs.pop('brief', None)
        return super().__init_subclass__(**kwargs)
    
    def __init__(self, bot: FuryBot, *args: Any, **kwargs: Any) -> None:
        self.bot: FuryBot = bot
        self.id: int = int(str(int(uuid.uuid4()))[:20])
        
        next_in_mro = next(iter(self.__class__.__mro__))
        if hasattr(next_in_mro, '__is_jishaku__') or isinstance(next_in_mro, self.__class__):
            kwargs['bot'] = bot
        
        super().__init__(*args, **kwargs)