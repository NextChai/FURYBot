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

import discord
from discord.ext import commands

__all__ = (
    'Confirmation',
    'Context',
)

class Confirmation(discord.ui.View):
    def __init__(self, author):
        super().__init__()
        self.value = False
        self.author = author
        
    async def interaction_check(self, interaction):
        return interaction.user == self.author
    
    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.Button, interaction: discord.Interaction) -> None:
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Cancelling', ephemeral=True)
        self.value = False
        self.stop()

class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def get_confirmation(self, *args, **kwargs) -> bool:
        """Get confirmation fromt he user.
        
        Parameters
        ----------
        args: List[Any]
            The args to pass onto the send function.
        kwargs: Dict[str, Any]
            The kwargs to pass onto the send function.
        
        Returns
        -------
        :class:`bool`
            True if confirmation was "Confirm" and false if confirmation was "Cancel". 
        """
        view = Confirmation(author=self.author)
        kwargs['view'] = view
        await self.send(*args, **kwargs)
        await view.wait()
        
        return view.value
        
    def tick(self, opt, label=None):
        lookup = {
            True: '✅',
            False: '❌',
            None: '❔',
        }
        emoji = lookup.get(opt, '❌')
        if label is not None:
            return f'{emoji}: {label}'
        return emoji