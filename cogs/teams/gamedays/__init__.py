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

import discord
from discord import app_commands

from utils import BaseCog

from .events import *
from .gameday import *
from .panel import *

if TYPE_CHECKING:
    from bot import FuryBot


class GamedayCommands(BaseCog):
    gameday = app_commands.Group(name='gameday', description='Commands for managing gamedays', guild_only=True)

    @gameday.command(name='upload', description='Upload supporting images for a gameday (such as score).')
    @app_commands.describe(attachment='The image to upload')
    async def gameday_upload(
        self, interaction: discord.Interaction[FuryBot], attachment: discord.Attachment
    ) -> discord.InteractionMessage:
        assert interaction.guild
        assert interaction.channel_id

        await interaction.response.defer(ephemeral=True)

        team = self.bot.get_team_from_channel(interaction.channel_id, interaction.guild.id)
        if not team:
            return await interaction.edit_original_response(content='This command can only be used in a team channel.')

        gameday = team.ongoing_gameday
        if gameday is None:
            return await interaction.edit_original_response(content='There is no ongoing gameday to upload to.')

        scoreboard_message_id = gameday.scoreboard_message_id
        if scoreboard_message_id is None:
            return await interaction.edit_original_response(content='There is no scoreboard message to upload to.')

        await GamedayImage.create(
            gameday, image_url=attachment.url, uploader_id=interaction.user.id, uploaded_at=interaction.created_at
        )

        # Let's edit the message, if it exists
        file = await gameday.merge_gameday_images()
        assert file

        partial = team.text_channel.get_partial_message(scoreboard_message_id)
        try:
            await partial.edit(embed=gameday.scoreboard.embed, attachments=[file])
        except discord.NotFound:
            return await interaction.edit_original_response(
                content='I added the image but I was unable to edit the scoreboard message as it no longer exists.'
            )

        return await interaction.edit_original_response(content='Successfully added the image.')


async def setup(bot: FuryBot):
    await bot.add_cog(GamedayEventListener(bot))
    await bot.add_cog(GamedayCommands(bot))
