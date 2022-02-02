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

from typing import Optional, Tuple, Union
import discord
from discord.ext import commands

__all__ = (
    'Confirmation',
    'Context',
)

class Confirmation(discord.ui.View):
    """Used to get confirmation from the user in a simple way.
    
    Attributes
    ----------
    value: :class:`bool`
        Denotes if the user has confirmed to the operation.
    author: Union[:class:`discord.Member`, :class:`discord.User`]
        The user who is confirming the operation.
    """
    __slots__: Tuple[str, ...] = (
        'value',
        'author'
    )
    
    def __init__(self, author: Union[discord.Member, discord.User]):
        super().__init__()
        self.value: bool = False
        self.author: Union[discord.Member, discord.User] = author
        
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


class DummyContext:
    """A dummy context used to convert human time without a context obj.
    
    Attributes
    ----------
    created_at: :class:`datetime.datetime`
        When the context was created.
    """
    __slots__: Tuple[str, ...] = (
        'created_at',
    )
    
    def __init__(self) -> None:
        self.created_at = discord.utils.utcnow()
    
    def __repr__(self) -> str:
        return '<DummyContext created_at={}>'.format(self.created_at)
        
class Context(commands.Context):
    """The overridden Context class. Used to provide some simple
    functionality to the bot, which can home in handy for commands.
    """
    __slots__: Tuple[str, ...] = ()
    
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
        
    def tick(self, opt: Optional[bool], label: Optional[str] = None) -> str:
        """Used to tick a message based on the operation.
        
        Parameters
        ----------
        opt: Optional[:class:`bool`]
            The operation to tick.
        label: Optional[:class:`str`]
            A label for the tick, if any.
            
        Returns
        -------
        :class:`str`
            The ticked message.
        """
        lookup = {
            True: '✅',
            False: '❌',
            None: '❔',
        }
        emoji = lookup.get(opt, '❌')
        
        if label is not None:
            return f'{emoji}: {label}'
        
        return emoji