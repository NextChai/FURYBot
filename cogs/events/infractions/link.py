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
from discord.ext import commands

from utils.bases.cog import BaseCog


def valid_message(message: discord.Message) -> bool:
    if not message.guild:
        return False
    if not isinstance(message.author, discord.Member):
        return False
    if not message.content:
        return False

    return True


class Link(BaseCog):
    @commands.Cog.listener('on_message')
    async def link_check(self, message: discord.Message) -> None:
        if not valid_message(message):
            return

        assert message.guild

        links = await self.bot.link_filter.get_links(message.content, guild_id=message.guild.id)
        if not links:
            return

        self.bot.dispatch('links_found', message, links)

    @commands.Cog.listener('on_message_edit')
    async def link_check_on_edit(self, before: discord.Message, after: discord.Message) -> None:
        if before.content == after.content:
            return

        if not valid_message(after):
            return

        assert after.guild

        links = await self.bot.link_filter.get_links(after.content, guild_id=after.guild.id)
        if not links:
            return

        self.bot.dispatch('links_found', after, links)
