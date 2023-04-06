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

import enum
from typing import TYPE_CHECKING, Tuple

__all__: Tuple[str, ...] = ('ScrimStatus',)

# Persistent views for team scrim confirmation from both
class ScrimStatus(enum.Enum):
    """
    An enum to represent the status of a scrim.

    pending_away: The away team has not yet confirmed the scrim.
    scheduled: The scrim has been scheduled.
    pending_host: The scrim is pending confirmation from the host.
    """

    pending_away = 'pending_away'
    scheduled = 'scheduled'
    pending_host = 'pending_host'


from .events import *
from .persistent import *
from .scrim import *

if TYPE_CHECKING:
    from bot import FuryBot


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ScrimEventListener(bot))