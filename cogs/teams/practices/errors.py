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

from typing import Tuple

__all__: Tuple[str, ...] = (
    'MemberNotInPractice',
    'MemberAlreadyInPractice',
    'MemberNotAttendingPractice',
)


class MemberNotInPractice(Exception):
    """Exception raised when a member is not in a practice session."""


class MemberAlreadyInPractice(Exception):
    """Exception raised when a member is already in a practice session."""


class MemberNotAttendingPractice(Exception):
    """Exception raised when a member is not attending a practice session but joins the voice channel during
    one."""
