import discord
from discord.ext import commands

__all__ = (
    'Confirmation',
    'Context',
)

class Confirmation(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = False
    
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
        view = Confirmation()
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