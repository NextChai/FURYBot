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
from typing_extensions import Self

from utils import BaseModal, default_button_doc_string

from .request import ImageRequest

if TYPE_CHECKING:
    from discord.interactions import InteractionChannel

    from bot import FuryBot


def mention_interaction_channel(channel: InteractionChannel) -> str:
    return f'<#{channel.id}>'


class DeniedImageReason(BaseModal):
    """A modal representing the moderator supplying the reason for denying an image.

    Parameters
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    parent: :class:`ApproveOrDenyImage`
        The parent view.
    request: :class:`ImageRequest`
        The image request that is being denied.
    """

    reason: discord.ui.TextInput[Self] = discord.ui.TextInput(
        label='Deny Reason',
        style=discord.TextStyle.long,
        custom_id='denied-image: reason',
        placeholder='Why was this image denied?',
    )

    def __init__(self, bot: FuryBot, parent: ApproveOrDenyImage, request: ImageRequest) -> None:
        super().__init__(bot, title='Deny an Upload')

        self.bot: FuryBot = bot
        self.parent: ApproveOrDenyImage = parent
        self.request: ImageRequest = request

    def _denied_embed(self, by: discord.abc.User) -> discord.Embed:
        user = self.request.requester

        embed = self.bot.Embed(
            title='Image has been denied.',
            description=f'This image upload from {user.mention} has been denied by a moderator, {by.mention}.',
            author=user,
        )
        embed.add_field(name='Deny Reason', value=self.reason.value)
        embed.add_field(name='Channel to Send In', value=mention_interaction_channel(self.request.channel))
        embed.set_image(url=f'attachment://{self.request.attachment.filename}')
        return embed

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> None:
        """|coro|

        Called when the modal has been submitted. This will deny the image request by sending a message to the requester
        with the information and deleting the request from the database.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from submitting the modal.
        """
        await interaction.response.defer()

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE images.requests SET denied_reason = $1 WHERE id = $2', self.reason.value, self.request.id
            )

        await interaction.edit_original_response(embed=self._denied_embed(by=interaction.user), view=None)


class ApproveOrDenyImage(discord.ui.View):
    """A view representing the moderator approving or denying an image.

    Parameters
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    request: :class:`ImageRequest`
        The image request that is being approved or denied.
    """

    def __init__(self, bot: FuryBot, request: ImageRequest) -> None:
        super().__init__(timeout=None)

        self.bot: FuryBot = bot
        self.request: ImageRequest = request

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed representing the image request."""
        embed = self.bot.Embed(
            title=f'Image requested by {self.request.requester.display_name}', author=self.request.requester
        )
        embed.add_field(name='Channel to Send in', value=mention_interaction_channel(self.request.channel))

        if self.request.message:
            embed.add_field(name='Additional Message', value=self.request.message, inline=False)

        embed.set_image(url=f'attachment://{self.request.attachment.filename}')

        return embed

    async def _approve(self, interaction: discord.Interaction[FuryBot]) -> Optional[discord.InteractionMessage]:
        request = self.request

        embed = self.bot.Embed(
            title='Image Approved',
            description=f'This image uploaded by {request.requester.mention} has been approved by a moderator, {interaction.user.mention}',
            author=request.requester,
            timestamp=interaction.created_at,
        )
        embed.add_field(name='Channel to Send In', value=mention_interaction_channel(self.request.channel))
        embed.set_image(url=f'attachment://{request.attachment.filename}')
        await interaction.edit_original_response(embed=embed, view=None)

        # Try and download the attachment as a file so we can send it that way
        try:
            file = await request.attachment.to_file(
                filename=f'file-upload-{request.requester.id}-{request.attachment.filename}'
            )
        except discord.NotFound:
            return await interaction.edit_original_response(
                content=f'The attachment was deleted before I could approve it, {interaction.user.mention}. You will need to upload it manually, if possible.',
            )
        except discord.HTTPException:
            return await interaction.edit_original_response(
                content=f'I was unable to download the attachment to approve it, {interaction.user.mention}. You will need to upload it manually.',
            )

        content = f'Uploaded by {request.requester.mention}.'
        if request.message:
            content += f' Message: {request.message}'

        # as of right now interaction.channel includes ForumChannel and CategoryChannel - it can not resolve to this though.
        assert not isinstance(request.channel, (discord.ForumChannel, discord.CategoryChannel))

        message = await request.channel.send(
            file=file, content=content, allowed_mentions=discord.AllowedMentions(users=[request.requester])
        )

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE images.requests SET message_id = $1 WHERE id = $2',
                message.id,
                self.request.id,
            )

        embed.add_field(name='Message Posted', value=f'[Jump to message]({message.jump_url})')
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label='Approve', style=discord.ButtonStyle.green, custom_id='approve')
    @default_button_doc_string
    async def approve(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        """Approves the image request by sending the image to the channel and deleting the request from the database."""
        await interaction.response.defer()

        await self._approve(interaction)

    @discord.ui.button(label='Approve Without Message', style=discord.ButtonStyle.gray, custom_id='approve-without-message')
    @default_button_doc_string
    async def approve_without_message(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Approves the image request by sending the image to the channel and deleting the request from the database. This
        will not send the message that was attached to the request. This comes in handy when the user has passed a message that
        is specific to the mods and shouldn't be shared with the rest of the server.
        """
        await interaction.response.defer()

        self.request.message = None
        await self._approve(interaction)

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.red, custom_id='deny')
    @default_button_doc_string
    async def deny(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Deny the image request by sending a message to the requester with the information and deleting the request from the database."""
        modal = DeniedImageReason(self.bot, self, self.request)
        return await interaction.response.send_modal(modal)
