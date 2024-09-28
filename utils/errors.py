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

from typing import Any, Tuple

from discord import app_commands

__all__: Tuple[str, ...] = (
    'ApplicationCommandException',
    'AutocompleteValidationException',
    'BadArgument',
    'TimerNotFound',
)


class ApplicationCommandException(app_commands.AppCommandError):
    """A custom exception raised when an operation fails in an application command's
    callback.

    This inherits :class:`discord.AppCommandError` and :class:`BotException`.

    Parameters
    ----------
    interaction: :class:`discord.Interaction`
        The interaction created from the command invocation.

    Attributes
    ----------
    interaction: :class:`discord.Interaction`
        The interaction created from the command invocation.
    """

    __slots__: Tuple[str, ...] = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


class AutocompleteValidationException(ApplicationCommandException):
    """An exception raised when validating the input from an autocomplete
    fails.

    This inherits :class:`ApplicationCommandException`.
    """


class BadArgument(ApplicationCommandException):
    """An exception raised when a command argument is invalid.

    This inherits :class:`ApplicationCommandException`.
    """


class TimerNotFound(BaseException):
    """An exception raised when a timer is not found.

    This inherits from :class:`BotException`

    Parameters
    ----------
    id: :class:`int`
        The ID of the timer that was not found.

    Attributes
    ----------
    id: :class:`int`
        The ID of the timer.
    """

    __slots__: Tuple[str, ...] = ('id',)

    def __init__(self, id: int) -> None:
        super().__init__(f'Timer {id} was not found!')
        self.id: int = id
