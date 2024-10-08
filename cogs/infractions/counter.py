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

import logging

import discord
from discord.ext import commands

from utils import RUNNING_DEVELOPMENT, BaseCog

_log = logging.getLogger(__name__)
if RUNNING_DEVELOPMENT:
    _log.setLevel(logging.DEBUG)


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
            _log.debug('Message is not of type auto_moderation_action. Message ID: %s', message.id)
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
            _log.debug('No infractions settings found for guild %s', guild.id)
            return

        if not settings.enable_infraction_counter:
            # Infraction counter is disabled
            _log.debug('Infraction counter is disabled for guild %s', guild.id)
            return

        # Check if the message was sent in the correct channel, ie the infractions notification channel
        notification_channel = settings.notification_channel
        if notification_channel and message.channel.id != notification_channel.id:
            _log.debug(
                'Message was not sent in the infractions notification channel. Message ID: %s, Channel ID: %s',
                message.id,
                message.channel.id,
            )
            return

        # We know the following:
        # (1) the message type is of auto_moderation_action
        # (2) the guild has settings
        # (3) the message was sent in the correct infractions notification channel, and
        # (4) the infraction counter is enabled
        # We can now proceed to increment the infraction counter for the member
        _log.debug('Adding infraction for user %s', message.author.id)
        await settings.add_infraction_for(message.author.id, in_channel=message.channel.id, message_id=message.id)
