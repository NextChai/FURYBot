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

from typing import TYPE_CHECKING, Optional

import discord
from typing_extensions import Self, Unpack

from utils import BaseModal, BaseView, BaseViewKwargs, ConfirmationGetter, default_button_doc_string

from .panel import AttachmentRequestSettingsPanel
from .request import ImageRequest
from .settings import AttachmentRequestSettings

if TYPE_CHECKING:
    from discord.interactions import InteractionChannel

    from bot import FuryBot


def mention_interaction_channel(channel: InteractionChannel) -> str:
    return f'<#{channel.id}>'


class DoesWantToCreateAttachmentSettings(BaseView):

    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)

        # Abuses the confirmation getter to do this for us nicely
        ConfirmationGetter(self._handle_response, self)

    @property
    def embed(self) -> discord.Embed:
        return self.bot.Embed(
            title='Attachment Request Settings',
            description='Would you like to create attachment request settings?',
        )

    async def _handle_response(
        self, interaction: discord.Interaction[FuryBot], should_create: bool
    ) -> discord.InteractionMessage:
        await interaction.response.defer()
        if not should_create:
            return await interaction.edit_original_response(
                content='Alright, no attachment settings will be created.', view=None, embed=None
            )

        if interaction.guild_id is None or interaction.channel_id is None:
            raise ValueError('Guild ID or Channel ID is None when trying to create attachment settings.')

        # TODO: Allow user to say where to create
        settings = await AttachmentRequestSettings.create(interaction.guild_id, interaction.channel_id, bot=self.bot)
        panel = AttachmentRequestSettingsPanel(settings, target=interaction)
        return await interaction.edit_original_response(embed=None, view=panel)


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
        if isinstance(request.channel, (discord.ForumChannel, discord.CategoryChannel)):
            raise ValueError('The channel cannot be sent to.')

        message = await request.channel.send(
            file=file, content=content, allowed_mentions=discord.AllowedMentions(users=[request.requester])
        )

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE images.requests SET message_id = $1 WHERE id = $2',
                message.id,
                self.request.id,
            )

        embed.add_field(name='Message Posted', value=f'[**Jump to Message**]({message.jump_url})', inline=False)
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
