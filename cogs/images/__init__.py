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

from typing import TYPE_CHECKING, Any, List, Optional, Dict

from bot import FuryBot
import nudenet
import discord
from discord import app_commands

from utils import BaseCog

from .request import ImageRequest, ImageRequestSettings
from .views import ApproveOrDenyImage

if TYPE_CHECKING:

    from bot import FuryBot


class ImageRequests(BaseCog):

    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)
        self._detector = nudenet.NudeDetector()

    async def _fetch_image_request_settings(self, guild_id: int) -> Optional[ImageRequestSettings]:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM images.request_settings WHERE guild_id = $1', guild_id)

        if not data:
            return None

        return ImageRequestSettings(data=dict(data), bot=self.bot)

    async def _append_nsfw_classification(self, embed: discord.Embed, file: discord.File) -> discord.Embed:
        data = file.fp.read()
        file.reset()

        detections: List[Dict[str, Any]] = await self.bot.wrap(self._detector.detect, data)
        nsfw_classifications: List[str] = []

        for detection in detections:
            score = detection['score']
            score_percent = round(score * 100, 2)
            class_name = detection["class"].replace('_', ' ').title()

            nsfw_classifications.append(f'{class_name}: **{score_percent}%**')

        if nsfw_classifications:
            embed.add_field(name='NSFW Classifications', value='\n'.join(nsfw_classifications))

        return embed

    @app_commands.command(name='attachment-request', description='Request to have an attachment uploaded for you.')
    @app_commands.default_permissions(attach_files=True)
    @app_commands.describe(
        attachment='The attachment you want to upload.',
        message='An optional message to send with the upload.',
        attachment2='The attachment (2) you want to upload.',
        attachment3='The attachment (3) you want to upload.',
        attachment4='The attachment (4) you want to upload.',
    )
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def attachment_request(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
        message: Optional[str] = None,
        attachment2: Optional[discord.Attachment] = None,
        attachment3: Optional[discord.Attachment] = None,
        attachment4: Optional[discord.Attachment] = None,
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
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        assert guild

        sender_channel = interaction.channel
        if not sender_channel:
            # Dpy has issues resolving this channel
            return await interaction.followup.send(
                'I was unable to resolve this channel. If the issue persists, please reach out for help.', ephemeral=True
            )

        # Try and resolve the image request settings from this guild first. If there are none then we need to
        # tell the user they cannot use this command
        settings = await self._fetch_image_request_settings(guild_id=guild.id)
        if settings is None:
            return await interaction.followup.send(
                'This server does not have image request settings enabled. Contact an admin to set it up!', ephemeral=True
            )

        attachments: List[Optional[discord.Attachment]] = [attachment, attachment2, attachment3, attachment4]

        # Denotes if an attachment request has been sent.
        # Used so that if there are 4 attachments the mods are not pinged 4 times.
        has_sent_request = False

        for pending_attachment in attachments:
            if pending_attachment is None:
                continue

            try:
                file = await pending_attachment.to_file(description=f'An upload by a {interaction.user.id}')
            except discord.HTTPException:
                # We weren't able to download the file
                return await interaction.edit_original_response(
                    content='I was unable to download this attachment. Please try with a different one or contact a moderator.'
                )

            # Create our request and view
            request = ImageRequest(
                requester=interaction.user, attachment=pending_attachment, channel=sender_channel, message=message
            )
            view = ApproveOrDenyImage(self.bot, request)

            content_type = pending_attachment.content_type
            if content_type and content_type.startswith('image/'):
                embed = await self._append_nsfw_classification(view.embed, file)
            else:
                embed = view.embed

            # Send the request to the channel
            channel = settings.channel
            if not channel:
                # The image request channel has been deleted, we need to complain!
                return await interaction.edit_original_response(
                    content='The image request channel has been deleted. Please contact a moderator to have this issue fixed.'
                )

            if has_sent_request:
                content = None
                allowed_mentions = discord.AllowedMentions()
            else:
                content = settings.notification_role and settings.notification_role.mention
                allowed_mentions = discord.AllowedMentions(
                    roles=[settings.notification_role] if settings.notification_role else []
                )

            moderator_message = await channel.send(
                view=view, embed=embed, content=content, file=file, allowed_mentions=allowed_mentions
            )

            # Insert into the DB now
            async with self.bot.safe_connection() as connection:
                data = await connection.fetchrow(
                    'INSERT INTO images.requests(created_at, attachment_payload, requester_id, channel_id, message, moderator_request_message_id) '
                    'VALUES ($1, $2, $3, $4, $5, $6) '
                    'RETURNING *',
                    interaction.created_at,
                    pending_attachment.to_dict(),
                    interaction.user.id,
                    sender_channel.id,
                    message,
                    moderator_message.id,
                )
                assert data

                request.id = data['id']

        # And alert the user of the request
        return await interaction.edit_original_response(
            content='I\'ve submitted the request for your attachment(s) to be uploaded.',
        )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ImageRequests(bot))
