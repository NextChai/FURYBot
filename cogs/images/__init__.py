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

import discord
from discord import app_commands

from utils import FURY_GUILD, IMAGE_NOTIFICATIONS_ROLE_ID, IMAGE_REQUEST_CHANNEL_ID, BaseCog

from .request import ImageRequest
from .views import ApproveOrDenyImage

if TYPE_CHECKING:

    from bot import FuryBot


class ImageRequests(BaseCog):
    @app_commands.command(name='attachment-request', description='Request to have an attachment uploaded for you.')
    @app_commands.default_permissions(attach_files=True)
    @app_commands.describe(
        attachment='The attachment you want to upload.',
        message='An optional message to send with the upload.',
    )
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    async def attachment_request(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
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
            # We're not in a guild OR its the incorrect guild. We need to yell at the user
            return await interaction.response.send_message("You must be in the FURY guild to use command.", ephemeral=True)

        sender_channel = interaction.channel
        if not sender_channel:
            # Dpy has issues resolving this channel
            return await interaction.response.send_message(
                'I was unable to resolve this channel. If the issue persists, please reach out for help.', ephemeral=True
            )

        # Defer because this could take a minute
        await interaction.response.defer(ephemeral=True)

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
            content='I\'ve submitted the request for this attachment to be uploaded. You will be notified if your request is approved.'
        )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ImageRequests(bot))
