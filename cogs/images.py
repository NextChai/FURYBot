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

from typing import TYPE_CHECKING, Optional, cast, Union
from typing_extensions import Self

import discord

from utils import default_button_doc_string, BaseCog, IMAGE_REQUEST_CHANNEL_ID, IMAGE_NOTIFICATIONS_ROLE_ID, BaseModal

from discord import app_commands

from utils.constants import FURY_GUILD

if TYPE_CHECKING:
    from bot import FuryBot


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
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread],
        message: Optional[str],
        id: Optional[int] = None,
    ) -> None:
        self.requester: discord.Member = requester
        self.attachment: discord.Attachment = attachment
        self.channel: Union[discord.TextChannel, discord.VoiceChannel, discord.Thread] = channel
        self.message: Optional[str] = message
        self.id: Optional[int] = id

    def __repr__(self) -> str:
        return f"ImageRequest(requester={self.requester!r}, attachment={self.attachment!r}, channel={self.channel!r}, message={self.message!r})"


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

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        """|coro|

        Called when the modal has been submitted. This will deny the image request by sending a message to the requester
        with the information and deleting the request from the database.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from submitting the modal.
        """
        user = self.request.requester

        embed = self.bot.Embed(
            title='Image has been denied.',
            description=f'This image upload from {user.mention} has been denied by a moderator, {interaction.user.mention}.',
            author=user,
        )
        embed.add_field(name='Deny Reason', value=self.reason.value)
        embed.add_field(name='Channel to Send In', value=self.request.channel.mention)
        await interaction.response.edit_message(embed=embed, view=None)

        # Send the reason to the user :blobpain:
        embed = self.bot.Embed(
            title='Upload Request Denied.',
            description=f'Your image upload request has been denied by a moderator, {interaction.user.mention}',
            author=user,
        )
        embed.add_field(name='Deny Reason', value=self.reason.value)

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM image_requests WHERE id = $1',
                self.request.id,
            )


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
        embed.add_field(
            name='Additional Message', value=self.request.message or "No message has been attached with this upload."
        )
        embed.add_field(name='Channel to Send in', value=self.request.channel.mention)

        return embed

    async def _approve(self, interaction: discord.Interaction) -> Optional[discord.InteractionMessage]:
        request = self.request

        embed = self.bot.Embed(
            title='Image Approved',
            description=f'This image uploaded by {request.requester.mention} has been approved by a moderator, {interaction.user.mention}',
            author=request.requester,
            timestamp=interaction.created_at,
        )
        embed.add_field(name='Channel to Send In', value=request.channel.mention)
        await interaction.edit_original_response(embed=embed, view=None)

        # Try and download the attachment as a file so we can send it that way
        try:
            file = await request.attachment.to_file(
                filename=f'file-upload-{request.requester.id}-{request.attachment.filename}'
            )
        except discord.NotFound:
            return await interaction.edit_original_response(
                content=f'The attachment was deleted before I could approve it, {interaction.user.mention}. You will need to upload it manually if possible!',
            )
        except discord.HTTPException:
            return await interaction.edit_original_response(
                content=f'I was unable to download the attachmen to approve it, {interaction.user.mention}. You will need to upload it manually!',
            )

        content = f'Uploaded by {request.requester.mention}.'
        if request.message:
            content += f' Message: {request.message}'

        message = await request.channel.send(
            file=file, content=content, allowed_mentions=discord.AllowedMentions(users=[request.requester])
        )

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM image_requests WHERE id = $1',
                self.request.id,
            )

        embed.add_field(name='Message Posted', value=f'[Jump to message]({message.jump_url})')
        await interaction.edit_original_response(embed=embed)

    @discord.ui.button(label='Approve', style=discord.ButtonStyle.green)
    @default_button_doc_string
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        """Approves the image request by sending the image to the channel and deleting the request from the database."""
        await interaction.response.defer()

        await self._approve(interaction)

    @discord.ui.button(label='Approve Without Message', style=discord.ButtonStyle.gray)
    @default_button_doc_string
    async def approve_without_message(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Approves the image request by sending the image to the channel and deleting the request from the database. This
        will not send the message that was attached to the request. This comes in handy when the user has passed a message that
        is specific to the mods and shouldn't be shared with the rest of the server.
        """
        await interaction.response.defer()

        self.request.message = None
        await self._approve(interaction)

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.red)
    @default_button_doc_string
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Deny the image request by sending a message to the requester with the information and deleting the request from the database."""
        modal = DeniedImageReason(self.bot, self, self.request)
        return await interaction.response.send_modal(modal)


class ImageRequests(BaseCog):
    @app_commands.command(name='attachment-request', description='Request to have an attachment uploaded for you.')
    @app_commands.default_permissions(attach_files=True)
    @app_commands.rename(channel_id='channel-id')
    @app_commands.describe(
        attachment='The attachment you want to upload.',
        channel_id='The ID of the channel you want the upload to send to.',
        message='An optional message to send with the upload.',
    )
    async def attachment_request(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
        channel_id: str,
        message: Optional[str] = None,
    ) -> Optional[discord.InteractionMessage]:
        """Allows a member to request an attachment to be uploaded for them.

        Parameters
        ----------
        attachment: :class:`discord.Attachment`
            The attachment to upload.
        channel_id: :class:`str`
            The ID of the channel to send the attachment to.
        message: Optional[:class:`str`]
            An optional message to send with the attachment.
        """
        # Both a moderator and a normal person can use this command.
        # Only mods can use it in a guild, and all others must use
        # it in DMS.
        if interaction.guild and interaction.guild.id == FURY_GUILD:
            # We're in a guild and its the correct one
            guild = interaction.guild
        else:
            # We're not in a guild OR its the incorrect guild, update
            guild = cast(discord.Guild, self.bot.get_guild(FURY_GUILD))

        if not channel_id.isdigit():
            # The value passed isnt correct for a channel
            return await interaction.response.send_message('The channel ID must be a number.')

        sender_channel = cast(
            Union[discord.TextChannel, discord.VoiceChannel, discord.Thread],
            guild.get_channel(int(channel_id)) or guild.get_thread(int(channel_id)),
        )
        if not sender_channel:
            # The channel doesnt exist
            return await interaction.response.send_message('The channel ID is invalid.')

        # Defer because this could take a minute
        await interaction.response.defer()

        try:
            file = await attachment.to_file(description=f'An upload by a {interaction.user.id}')
        except discord.HTTPException:
            # We weren't able to download the file
            return await interaction.edit_original_response(
                content='I was unable to download this attachment. Please try with a different one or contact a moderator.'
            )

        member = interaction.user
        if not isinstance(member, discord.Member):
            # If the command is invoked in DMS, we won't have a member.
            # This is useful for when we want to display the user's name
            # in an embed (with nickname)
            member = guild.get_member(member.id) or await guild.fetch_member(member.id)

        # Create our request and view
        request = ImageRequest(requester=member, attachment=attachment, channel=sender_channel, message=message)
        view = ApproveOrDenyImage(self.bot, request)

        # Send the request to the channel
        channel = cast(discord.TextChannel, guild.get_channel(IMAGE_REQUEST_CHANNEL_ID))
        role = guild.get_role(IMAGE_NOTIFICATIONS_ROLE_ID)
        if not channel or not role:
            # Something's veery wrong
            return await interaction.edit_original_response(content='Unable to find the image request channel!')

        message_obj = await channel.send(
            view=view,
            embed=view.embed,
            content=role.mention,
            file=file,
            allowed_mentions=discord.AllowedMentions(roles=[role]),
        )

        # Insert into the DB now
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO image_requests(attachment_payload, requester_id, guild_id, channel_id, message_id, message) '
                'VALUES ($1, $2, $3, $4, $5, $6) '
                'RETURNING *',
                attachment.to_dict(),
                interaction.user.id,
                guild.id,
                sender_channel.id,
                message_obj.id,
                message,
            )
            assert data

            request.id = data['id']

        # And alert the user of the request
        return await interaction.edit_original_response(
            content=f'I\'ve submitted the request for this attachment to be uploaded. You will be notified if it gets approved '
            'or denied.'
        )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ImageRequests(bot))
