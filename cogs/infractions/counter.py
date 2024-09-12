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

import logging

import discord
from discord.ext import commands

from utils import BaseCog

_log = logging.getLogger(__name__)


class InfractionCounter(BaseCog):
    """Represents an infraction counter. Will keep track of the amount
    of infractions a given member has.

    What qualifies as an infraction? That is,
    - Any auto mod action sent in the infractions notification channel (infractions.settings.notification_channel_id) (:meth:`InfractionSettings.notification_channel`). This means that
    the auto-mod system must have messages enabled to the same notifications channel.
    - .... more to be added later (?)
    """

    @commands.Cog.listener('on_message')
    async def auto_mod_action_water(self, message: discord.Message) -> None:
        if message.type != discord.MessageType.auto_moderation_action:
            # Not of correct type
            return

        guild = message.guild
        if not guild:
            # This, ideally, should never happen
            return _log.warning(
                'Auto-mod action message was send in DM channel (?). Message ID: %s, Channel ID: %s',
                message.id,
                message.channel.id,
            )

        settings = self.bot.get_infractions_settings(guild.id)
        if not settings:
            # No settings found
            return

        if not settings.enable_infraction_counter:
            # Infraction counter is disabled
            return

        # Check if the message was sent in the correct channel, ie the infractions notification channel
        notification_channel = settings.notification_channel
        if notification_channel and message.channel.id != notification_channel.id:
            return

        # We know the following:
        # (1) the message type is of auto_moderation_action
        # (2) the guild has settings
        # (3) the message was sent in the correct infractions notification channel, and
        # (4) the infraction counter is enabled
        # We can now proceed to increment the infraction counter for the member
        await settings.add_infraction_for(message.author.id, in_channel=message.channel.id, message_id=message.id)
