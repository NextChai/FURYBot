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

import enum
from typing import Tuple

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
