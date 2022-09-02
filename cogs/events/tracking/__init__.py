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
import re
from typing import TYPE_CHECKING, List, Optional, Union

import cachetools
import discord
from discord.ext import commands

from utils.bases.cog import BaseCog
from utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot


class MessageTracker(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.message_cache: cachetools.Cache[int, discord.Message] = cachetools.Cache(maxsize=5000)

        self.message_webhook: Optional[discord.Webhook] = None
        self.message_webhook_cache: cachetools.Cache[int, Union[discord.WebhookMessage, discord.Message]] = cachetools.Cache(
            maxsize=5000
        )

    async def fetch_webhook(self) -> discord.Webhook:
        match = re.search(
            r'discord(?:app)?.com/api/webhooks/(?P<id>[0-9]{17,20})/(?P<token>[A-Za-z0-9\.\-\_]{60,68})',
            os.environ['MESSAGE_WEBHOOK_URL'],
        )
        assert match

        return await self.bot.fetch_webhook(int(match['id']))

    @commands.Cog.listener('on_message')
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return
        if message.webhook_id:
            return
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return

        self.message_cache[message.id] = message

        if not self.message_webhook:
            self.message_webhook = await self.fetch_webhook()

        if message.channel.id == self.message_webhook.channel_id:
            return

        files: List[discord.File] = []
        if message.attachments:
            for attachment in message.attachments:
                try:
                    file = await attachment.to_file()
                except Exception:
                    continue

                files.append(file)

        webhook_message = await self.message_webhook.send(
            content=message.content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
            files=files,
            embeds=message.embeds,
            allowed_mentions=discord.AllowedMentions.none(),
            wait=True,
        )
        self.message_webhook_cache[message.id] = webhook_message

    @commands.Cog.listener('on_message_edit')
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if all(
            (
                before.content == after.content,
                before.embeds == after.embeds,
            )
        ):
            return

        # See if we can find from the webhook cache
        webhook_message = self.message_webhook_cache.get(after.id, None)
        if webhook_message is None:
            return

        embed = self.bot.Embed(title='Edited Message', author=after.author, description=after.content)

        embeds = [embed]
        embeds.extend(after.embeds)

        new_message = await webhook_message.reply(
            embeds=embeds,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.message_webhook_cache[after.id] = new_message

    @commands.Cog.listener('on_message_delete')
    async def on_message_delete(self, message: discord.Message) -> None:
        webhook_message = self.message_webhook_cache.get(message.id)
        if not webhook_message:
            return

        embed = self.bot.Embed(title='Message has been deleted.', description=webhook_message.content)
        embeds = [embed]
        embeds.extend(webhook_message.embeds)

        await webhook_message.reply(embeds=embeds)
        self.message_webhook_cache.pop(message.id)

    @commands.command(name='snipe', description='Snipe a deleted message.')
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def snipe(self, ctx: Context, private: bool = False) -> discord.Message:
        assert ctx.guild

        # Let's find the first message
        messages = list(self.message_cache.values()).copy()
        messages.sort(key=lambda m: m.created_at, reverse=True)

        message = discord.utils.find(
            lambda message: message.channel == ctx.channel and self.bot._connection._get_message(message.id) is None,
            messages,
        )
        sender = ctx.author.send if private else ctx.send
        if not message:
            return await sender(f'No cached message was found in {ctx.channel.mention}')  # pyright: ignore

        embed = self.bot.Embed(
            author=message.author, title='Sniped Message', description=message.content, timestamp=message.created_at
        )
        embed.add_field(
            name='Attachments', value='\n'.join([f'- {att.url}' for att in message.attachments] or ['No attachments.'])
        )
        embed.add_field(name='Embeds', value=bool(message.embeds) or 'Message contained no embeds.')
        return await sender(embed=embed)


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(MessageTracker(bot))
