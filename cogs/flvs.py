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

import os
from typing import TYPE_CHECKING, Final, List, Union

import cachetools
import discord
from discord.ext import commands

from utils import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot

FURY_GUILD: Final[int] = 757664675864248360


class FLVS(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.message_cache: cachetools.Cache[int, discord.Message] = cachetools.Cache(maxsize=5000)

        self.message_webhook_cache: cachetools.Cache[int, Union[discord.WebhookMessage, discord.Message]] = cachetools.Cache(
            maxsize=5000
        )

    # START OF FURY MESSAGE LOGGER

    # Part of the Fury custom tools is a unique message logger that logs every message sent in the server to a specific
    # channel using webhooks. This is essentially API abuse so it will not be used in any other part of the bot other than this
    # specific feature for a single guild.

    @property
    def fury_message_webhook(self) -> discord.Webhook:
        return discord.Webhook.from_url(url=os.environ['MESSAGE_WEBHOOK_URL'], session=self.bot.session, client=self.bot)

    # Watches for new messages and sends them to the logger
    @commands.Cog.listener('on_message')
    async def fury_message_logger(self, message: discord.Message) -> None:
        guild = message.guild
        if not guild or guild.id != FURY_GUILD:
            return
        if message.webhook_id:
            return
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        if message.author.bot:
            return

        self.message_cache[message.id] = message

        if message.channel.id == self.fury_message_webhook.channel_id:
            return

        files: List[discord.File] = []
        if message.attachments:
            for attachment in message.attachments:
                try:
                    file = await attachment.to_file()
                except Exception:
                    continue

                files.append(file)

        if not files and not message.embeds and not message.content:
            return

        webhook_message = await self.fury_message_webhook.send(
            content=message.content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            files=files,
            embeds=message.embeds,
            allowed_mentions=discord.AllowedMentions.none(),
            wait=True,
        )
        self.message_webhook_cache[message.id] = webhook_message

    # Watches for an edited message and sends a notification to the logger letting people
    # know this message has been updated
    @commands.Cog.listener('on_message_edit')
    async def fury_message_logger_updater(self, before: discord.Message, after: discord.Message) -> None:
        if not after.guild or after.guild != self.bot.get_guild(FURY_GUILD):
            return

        if all(
            (
                before.content == after.content,
                before.embeds == after.embeds,
            )
        ):
            return

        embed = self.bot.Embed(title='Edited Message', author=after.author, description=after.content)
        embeds = [embed]
        embeds.extend(after.embeds)

        # See if we can find from the webhook cache
        webhook_message = self.message_webhook_cache.get(after.id, None)
        if webhook_message is None:
            new_message = await self.fury_message_webhook.send(
                content=after.content,
                username=after.author.display_name,
                avatar_url=after.author.display_avatar.url,
                embeds=embeds,
                allowed_mentions=discord.AllowedMentions.none(),
                wait=True,
            )
        else:

            new_message = await webhook_message.reply(
                embeds=embeds,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        self.message_webhook_cache[after.id] = new_message

    # END OF FURY MESSAGE LOGGER


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(FLVS(bot))
