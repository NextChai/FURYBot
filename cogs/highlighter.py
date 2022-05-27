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

import re
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
    Any
)

import discord
from discord.ext import commands

from utils import BaseCog, clamp
from utils.context import Context
from utils.paginator import BaseButtonPaginator

if TYPE_CHECKING:
    from asyncpg import Record

    from bot import FuryBot


def to_lower(argument: str) -> str:
    return argument.lower()


class HighlightPaginator(BaseButtonPaginator):
    def __init__(self, bot: FuryBot, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bot: FuryBot = bot

    async def format_page(self, entries: List[Record]) -> discord.Embed:
        embed = self.bot.Embed(
            title='Highlighed Phrases', description='\n'.join(f'{entry["phrase"]} ({entry["id"]})' for entry in entries)
        )
        return embed


class Highlighter(BaseCog, brief='The commands that allow you to highlight phrases in the chat.', emoji='\N{BELLHOP BELL}'):
    @commands.command(
        name='highlights',
        brief='View all highlights',
        description='View all highlights',
    )
    async def highlights(
        self,
        ctx: Context,
    ) -> Optional[discord.Message]:
        data = self.bot.highlight_cache.get(ctx.author.id)
        if not data:
            return await ctx.send('You have no highlights.')

        await HighlightPaginator.start(ctx, entries=data)

    @commands.group(
        name='highlight',
        brief='Highlight messages sent from the server.',
        description='Highlight messages sent from the server about a specific topic.',
        invoke_without_command=True,
    )
    async def highlight(
        self,
        ctx: Context,
        count: Optional[int] = commands.parameter(converter=Optional[clamp], default=5),  # type: ignore
        *,
        phrase: str = commands.parameter(converter=to_lower),
    ) -> Optional[discord.Message]:
        if ctx.invoked_subcommand:
            return

        current = self.bot.highlight_cache.get(ctx.author.id)
        if current and phrase in (entry['phrase'] for entry in current):
            return await ctx.send(f'The phrase, `{phrase}`, is already highlighted.')

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO highlight (phrase, member, count) VALUES ($1, $2, $3) RETURNING *', phrase, ctx.author.id, count
            )

        if current:
            current.append(dict(data))
        else:
            self.bot.highlight_cache[ctx.author.id] = [dict(data)]

        await ctx.send(f'You will now be highlighted for messages containing `{phrase}`.')

    @highlight.command(
        name='add',
        brief='Add a highlight',
        description='Add a highlight',
        aliases=['+'],
    )
    async def highlight_add(
        self,
        ctx: Context,
        count: int = commands.parameter(converter=Optional[clamp], default=5),  # type: ignore
        *,
        phrase: str = commands.parameter(converter=to_lower),
    ) -> Optional[discord.Message]:
        return await self.highlight(ctx, count, phrase=phrase)

    @highlight.command(
        name='remove',
        brief='Remove a highlight',
        description='Remove a phrase from being highlighted',
        aliases=['-'],
    )
    async def highlight_remove(
        self, ctx: Context, *, phrase: str = commands.parameter(converter=to_lower)
    ) -> Optional[discord.Message]:
        current = self.bot.highlight_cache.get(ctx.author.id)
        if not current:
            return await ctx.send('You have no highlights.')

        if phrase not in (entry['phrase'] for entry in current):
            return await ctx.send(f'The phrase, `{phrase}`, is not highlighted.')

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM highlight WHERE phrase = $1 AND member = $2', phrase, ctx.author.id)

        self.bot.highlight_cache[ctx.author.id] = [entry for entry in current if entry['phrase'] != phrase]
        return await ctx.send(f'You will no longer be highlighted for messages containing `{phrase}`.')

    @commands.Cog.listener('on_message')
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return None
        if message.author.bot:
            return

        content = message.content and message.content.lower()
        if content is None:
            return

        history = None
        for member_id, data in self.bot.highlight_cache.items():
            if member_id == message.author.id:
                continue

            # Let's build a regex
            regex_string = '|'.join(f'({entry["phrase"]})' for entry in data)

            # Now let's check if the message matches
            if not (match := re.search(regex_string, content, re.IGNORECASE)):
                continue

            grouper = match.groups(0)
            try:
                phrase = grouper[0]
            except IndexError:
                continue

            item = discord.utils.find(lambda e: e['phrase'] == phrase, data)
            if not item:
                continue

            # We found a match!
            if not history:
                history = [message async for message in message.channel.history(limit=item['count'], before=message)]

            # Now let's build an embed
            channel_name = getattr(message.channel, 'name', None) or '_'  # note: "_" cant happen but for type checker

            embed = self.bot.Embed(
                title=f'"{phrase}" highlighted in #{channel_name}',
                description=f'Highlighted by {message.author.mention} - [jump!]({message.jump_url})',
            )
            embed.set_author(name=message.guild.name, icon_url=message.guild.icon.url)  # type: ignore

            fmt = [f'**{str(his.author)}**: {his.content}' for his in history]
            embed.add_field(name='Content', value='\n'.join(fmt) + f'\n**{str(message.author)}: {message.content}**')

            try:
                user = self.bot.get_user(member_id) or (await self.bot.fetch_user(member_id))
            except:
                continue

            try:
                await user.send(embed=embed)
            except Exception:
                continue


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Highlighter(bot))
