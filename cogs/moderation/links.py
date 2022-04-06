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

from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

import discord
from discord.ext import commands

from utils import BaseCog
from utils.context import Context

def _link_join(links: List[str]) -> str:
    return '\n'.join(f'[`link{index+1}`]({link})' for index, link in enumerate(links))

def _maybe_plural(count: int) -> str:
    return 's' if count > 1 else ''

class Link(BaseCog):
    
    @commands.group(
        name='link',
        brief='Manage the link filter',
        description='Manage the link filter',
        aliases=['linkfilter', 'links'],
        invoke_without_command=True
    )
    async def link(self, ctx: Context, *, phrase: str) -> None:
        if ctx.invoked_subcommand:
            return
        
        links = await self.bot.get_links(phrase)
        link_fmt = [f'[`{"link" + str(index+1)}`]({link}) ({await self.bot.is_valid_link(link)})' for index, link in enumerate(links)]
        embed = self.bot.Embed(
            description='**Link (Allowed?)**\n' + '\n'.join(link_fmt or ['No links found.']),
            author=ctx.author
        )
        await ctx.send(embed=embed)
    
    @link.command(
        name='add',
        brief='Add a link to the list of links',
        description='Add a link to the list of links',
        aliases=['+']
    )
    async def link_add(self, ctx: Context, *, link: str) -> Optional[discord.Message]:
        # Let's verify there's links in the phrase
        links = await self.bot.get_links(link)
        if not links:
            return await ctx.send('There were no links found in that phrase.')
        
        already_links = []
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM links')
            db_links = [entry['link'] for entry in data]
        
            for link in links:
                if link in db_links:
                    already_links.append(link)
                    links.remove(link)
                
            await connection.executemany('INSERT INTO links (url) VALUES ($1)', [(link,) for link in links])
        
        self.bot.links._allowed_links = None
        
        embed = self.bot.Embed(
            title='{} Link{} Added'.format(len(links), _maybe_plural(len(links))),
            description=_link_join(links),
        )
        
        if already_links:
            embed.add_field(
                name='Link{} already in database'.format(_maybe_plural(len(already_links))),
                value=_link_join(already_links)
            )
        
        return await ctx.send(embed=embed)
    
    @link.command(
        name='remove',
        brief='Remove a link from the list of links',
        description='Remove a link from the list of links',
        aliases=['-']
    )
    async def link_remove(self, ctx: Context, *, link: str) -> Optional[discord.Message]:
        links = await self.bot.get_links(link)
        if not links:
            return await ctx.send('There were no links found in that phrase.')
        
        not_links = []
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM links')
            db_links = [entry['url'] for entry in data]
            
            for link in links:
                if link not in db_links:
                    not_links.append(link)
                    links.remove(link)
        
            await connection.executemany('DELETE FROM links WHERE url = $1', [(link,) for link in links])

        self.bot.links._allowed_links = None

        embed = discord.Embed(
            title='Removed {} Link{}'.format(len(links), _maybe_plural(len(links))),
            description=_link_join(links) or 'No links.',
        )
        
        if not_links:   
            embed.add_field(
                name='Link{} not in database'.format(_maybe_plural(len(not_links))),
                value=_link_join(links) or 'No links.'
            )
        
        await ctx.send(embed=embed)