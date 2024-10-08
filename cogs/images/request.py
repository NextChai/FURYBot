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

from typing import TYPE_CHECKING, Optional, Union

import discord

if TYPE_CHECKING:
    from discord.interactions import InteractionChannel


class ImageRequest:
    """Represents an image request so that it can be used in child views easier.

    .. container:: operations

        .. describe:: repr(x)

            Returns the representation of the image request.

    Parameters
    Attributes
    ----------
    requester: :class:`discord.Member`
        The member who requested the image.
    attachment: :class:`discord.Attachment`
        The attachment that was requested to be uploaded.
    channel: Union[:class:`discord.TextChannel`, :class:`discord.VoiceChannel`, :class:`discord.Thread`]
        The channel that the image should be sent to.
    message: Optional[:class:`str`]
        A custom message to be sent with the image.
    id: Optional[:class:`int`]
        The ID of the image request. This shouldn't be None unless the database hasn't been inserted into yet.
    """

    def __init__(
        self,
        requester: Union[discord.User, discord.Member],
        attachment: discord.Attachment,
        channel: InteractionChannel,
        message: Optional[str],
        id: Optional[int] = None,
    ) -> None:
        self.requester: Union[discord.User, discord.Member] = requester
        self.attachment: discord.Attachment = attachment
        self.channel: InteractionChannel = channel
        self.message: Optional[str] = message
        self.id: Optional[int] = id

    def __repr__(self) -> str:
        return f"<ImageRequest requester={self.requester!r}, attachment={self.attachment!r}, channel={self.channel!r}, message={self.message!r}>"
