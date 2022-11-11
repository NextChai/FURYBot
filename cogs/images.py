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
from typing import TYPE_CHECKING, Optional, cast
from typing_extensions import Self

import discord

from utils import BaseCog, IMAGE_REQUEST_CHANNEL_ID, IMAGE_NOTIFICATIONS_ROLE_ID, BaseModal

from discord import app_commands

if TYPE_CHECKING:
    from bot import FuryBot


class ImageRequest:
    def __init__(
        self,
        requester: discord.Member,
        attachment: discord.Attachment,
        channel: discord.abc.Messageable,
        message: Optional[str],
        id: Optional[int] = None,
    ) -> None:
        self.requester: discord.Member = requester
        self.attachment: discord.Attachment = attachment
        self.channel: discord.abc.Messageable = channel
        self.message: Optional[str] = message
        self.id: Optional[int] = id

    def __repr__(self) -> str:
        return f"ImageRequest(requester={self.requester!r}, attachment={self.attachment!r}, channel={self.channel!r}, message={self.message!r})"


class DeniedImageReason(BaseModal):
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
        user = self.request.requester

        embed = self.bot.Embed(
            title='Image has been denied.',
            description=f'This image upload from {user.mention} has been denied by a moderator, {interaction.user.mention}.',
            author=user,
        )
        await interaction.response.edit_message(embed=self.parent.embed, view=None)

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
    def __init__(self, bot: FuryBot, request: ImageRequest) -> None:
        super().__init__(timeout=None)

        self.bot: FuryBot = bot
        self.request: ImageRequest = request

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'Image requested by {self.request.requester.display_name}', author=self.request.requester
        )
        embed.add_field(
            name='Additional Message', value=self.request.message or "No message has been attached with this upload."
        )

        return embed

    @discord.ui.button(label='Approve', style=discord.ButtonStyle.green)
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        await interaction.response.defer()

        # Try and download the attachment as a file so we can send it that way
        request = self.request
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

        await request.channel.send(
            file=file, content=content, allowed_mentions=discord.AllowedMentions(users=[request.requester])
        )

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM image_requests WHERE id = $1',
                self.request.id,
            )

        embed = self.bot.Embed(
            title='Image Approved',
            description=f'This image uploaded by {request.requester.mention} has been approved by a moderator, {interaction.user.mention}',
            author=request.requester,
            timestamp=interaction.created_at,
        )

        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label='Deny', style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        modal = DeniedImageReason(self.bot, self, self.request)
        return await interaction.response.send_modal(modal)


class ImageRequests(BaseCog):
    @app_commands.command(name='attachment-request', description='Request to have an attachment uploaded for you.')
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    async def attachment_request(
        self, interaction: discord.Interaction, attachment: discord.Attachment, message: Optional[str] = None
    ) -> discord.InteractionMessage:
        assert isinstance(interaction.user, discord.Member)
        assert isinstance(interaction.channel, discord.abc.Messageable)
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        try:
            file = await attachment.to_file(description=f'An upload by a {interaction.user.id}')
        except discord.HTTPException:
            return await interaction.edit_original_response(
                content='I was unable to download this attachment. Please try with a different one or contact a moderator.'
            )

        # Build a request
        request = ImageRequest(
            requester=interaction.user, attachment=attachment, channel=interaction.channel, message=message
        )
        view = ApproveOrDenyImage(self.bot, request)

        # Send the request to the channel
        channel = cast(discord.TextChannel, interaction.guild.get_channel(IMAGE_REQUEST_CHANNEL_ID))
        role = interaction.guild.get_role(IMAGE_NOTIFICATIONS_ROLE_ID)
        if not channel or not role:
            return await interaction.edit_original_response(content='Unable to find the image request channel!')

        message_obj = await channel.send(
            view=view,
            embed=view.embed,
            content=role.mention,
            file=file,
            allowed_mentions=discord.AllowedMentions(roles=[role]),
        )

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO image_requests(attachment_payload, requester_id, guild_id, channel_id, message_id, message) '
                'VALUES ($1, $2, $3, $4, $5, $6) '
                'RETURNING *',
                attachment.to_dict(),
                interaction.user.id,
                interaction.guild.id,
                interaction.channel.id,
                message_obj.id,
                message,
            )
            assert data

            request.id = data['id']

        return await interaction.edit_original_response(
            content=f'I\'ve submitted the request for this attachment to be uploaded. You will be notified if it gets approved '
            'or denied.'
        )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ImageRequests(bot))
