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

import textwrap
import logging
from urllib.parse import urlparse
from typing import TYPE_CHECKING, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog

from .actions import *

if TYPE_CHECKING:
    from bot import FuryBot

_log = logging.getLogger(__name__)


class Links(BaseCog):
    
    @app_commands.command(name='links')
    @app_commands.default_permissions(manage_messages=True)
    async def links(self, interaction: discord.Interaction[FuryBot]) -> None:
        raise NotImplementedError
    
    def should_check_message(self, message: discord.Message) -> bool:
        if message.author.bot:
            return False

        if message.guild is None:
            return False

        if message.webhook_id:
            return False

        if not message.content:
            return False

        return True

    async def handle_found_links(
        self, message: discord.Message, settings: LinkSettings, links: List[Tuple[str, Tuple[int, int]]]
    ) -> None:

        for action in settings.actions:
            if action.type is LinkActionType.surpress:
                await message.delete()
            elif action.type is LinkActionType.warn:
                await message.channel.send(f'{message.author.mention}, {action.warn_message}')                
            elif action.type is LinkActionType.mute:
                if isinstance(message.author, discord.Member):
                    await message.author.timeout(action.delta, reason='Link Filter auto mute.')

        notifier_channel = settings.notifier_channel
        if notifier_channel is None:
            return
        
        assert not isinstance(message.channel, (discord.DMChannel, discord.PartialMessageable, discord.GroupChannel))
        assert isinstance(notifier_channel, discord.abc.Messageable)
        
        embed = self.bot.Embed(
            title='Links Found',
            description=f'**{len(links)} links** have been found in a message posted by {message.author.mention} in '
            f'{message.channel.mention}'
        )
        embed.add_field(
            name='Message Content',
            value=textwrap.shorten(message.content, 1024, placeholder='...'),
            inline=False
        )
        embed.add_field(
            name='Links Found',
            value=textwrap.shorten(
                '\n'.join([
                    f'[{urlparse(link).netloc or link}]({link}) ({start}:{end})' for link, (start, end) in links
                ]),
                1024,
                placeholder='...'
            ),
            inline=False
        )

        await notifier_channel.send(embed=embed)

    @commands.Cog.listener('on_message')
    async def on_message(self, message: discord.Message) -> None:
        if not self.should_check_message(message):
            return

        assert message.guild

        settings = self.bot.get_link_setting(message.guild.id)
        if settings is None:
            # This guild does not use the link filter
            return

        if not settings.actions:
            # This guild has settings but no actions, do nothing
            return

        # Let's check for links here
        links = await self.bot.link_filter.fetch_links(message.content, guild_id=message.guild.id)
        if not links:
            _log.debug(f'Message %s did not contain any links.', message.id)
            return

        await self.handle_found_links(message, settings, links)
        
    @commands.Cog.listener('on_message_edit')
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not self.should_check_message(after):
            return
        
        if before.content == after.content:
            return

        assert after.guild

        settings = self.bot.get_link_setting(after.guild.id)
        if settings is None:
            # This guild does not use the link filter
            return

        if not settings.actions:
            # This guild has settings but no actions, do nothing
            return

        # Let's check for links here
        links = await self.bot.link_filter.fetch_links(after.content, guild_id=after.guild.id)
        if not links:
            _log.debug(f'Message %s did not contain any links.', after.id)
            return

        await self.handle_found_links(after, settings, links)


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Links(bot))
