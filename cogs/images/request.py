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

from typing import TYPE_CHECKING, Optional

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
        requester: discord.Member,
        attachment: discord.Attachment,
        channel: InteractionChannel,
        message: Optional[str],
        id: Optional[int] = None,
    ) -> None:
        self.requester: discord.Member = requester
        self.attachment: discord.Attachment = attachment
        self.channel: InteractionChannel = channel
        self.message: Optional[str] = message
        self.id: Optional[int] = id

    def __repr__(self) -> str:
        return f"<ImageRequest requester={self.requester!r}, attachment={self.attachment!r}, channel={self.channel!r}, message={self.message!r}>"
