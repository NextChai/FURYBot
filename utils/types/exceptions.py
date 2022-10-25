from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    import datetime

__all__: Tuple[str, ...] = ('Traceback', 'TracebackOptional')


class TracebackOptional(TypedDict, total=False):
    author: Optional[int]
    guild: Optional[int]
    channel: Optional[int]
    command: Optional[Any]
    gist: Optional[str]


class Traceback(TracebackOptional):
    time: datetime.datetime
    exception: Exception
    event_name: NotRequired[str]
