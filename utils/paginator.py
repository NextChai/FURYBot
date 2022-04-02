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

import asyncio
from typing import (
    Any,
    Coroutine,
    List,
    Tuple,
    Union
)

import discord
from discord.ext import commands


class IncompletePaginator(commands.Paginator):
    def partially_close_page(self) -> str:
        current = self._current_page.copy()
        if self.suffix is not None:
            current.append(self.suffix)
        
        return self.linesep.join(current)
    
    @property
    def incomplete_pages(self) -> List[str]:
        if len(self._current_page) > (0 if self.prefix is None else 1):
            page = self.partially_close_page()
            new_pages = self._pages.copy()
            new_pages.append(page)
            return new_pages
            
        return self._pages
    
    
class AsyncCodePaginator(discord.ui.View, IncompletePaginator):
    __slots__: Tuple[str, ...] = (
        'message',
        'current',
    )
    
    def __init__(self, message: discord.Message, author: Union[discord.Member, discord.User], timeout: float = 180.0, *args, **kwargs) -> None:
        super().__init__(timeout=timeout)
        IncompletePaginator.__init__(self, *args, **kwargs)
        
        self.author: Union[discord.Member, discord.User] = author
        self.message: discord.Message = message
        self.current: int = 0
        
    def __repr__(self) -> str:
        return '<AsyncCodePaginator interaction={0.interaction} current={0.current}>'.format(self)
    
    def __await__(self):
        return self.add_line.__await__()
    
    def __call__(self, line: str) -> Coroutine[Any, Any, None]:
        return self.add_line(line)
    
    @property
    def current_page(self) -> str:
        return self.incomplete_pages[self.current]
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def add_line(self, line: str) -> None:
        super().add_line(line)
        self.current = len(self.incomplete_pages) - 1 if self.incomplete_pages else 0
        
        await self.message.edit(content=self.current_page, view=self)
    
    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK LEFT-POINTING TRIANGLE}'), style=discord.ButtonStyle.primary)
    async def backward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current > 0:
            self.current -= 1
        else:
            self.current = len(self.incomplete_pages) - 1
        
        return await interaction.response.edit_message(content=self.current_page, view=self)
    
    @discord.ui.button(emoji=discord.PartialEmoji(name='\N{BLACK RIGHT-POINTING TRIANGLE}'), style=discord.ButtonStyle.primary)
    async def forward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current < len(self.incomplete_pages) - 1:
            self.current += 1
        else:
            self.current = 0
        
        return await interaction.response.edit_message(content=self.current_page, view=self)
    
    @discord.ui.button(label='Stop Pagination', style=discord.ButtonStyle.danger)
    async def stop_pagination(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True # type: ignore
        
        self.stop()
        await interaction.response.edit_message(view=self)