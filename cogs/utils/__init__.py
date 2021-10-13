from .checks import *
from .constants import *
from .context import *
from .enums import *
from .errors import *
from .profanity_filter import *
from .time import *

from typing import Callable, TypeVar
from inspect import signature 

T = TypeVar('T')

def copy_doc(original: Callable) -> Callable[[T], T]:
    def decorator(overriden: T) -> T:
        if overriden.__doc__:
            overriden.__doc__ = f'{overriden.__doc__}\n{original.__doc__}'
        else:
            overriden.__doc__ = original.__doc__
            
        overriden.__signature__ = signature(original)  # type: ignore
        return overriden

    return decorator