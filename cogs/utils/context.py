import discord
from discord.ext import commands

class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Cancelling', ephemeral=True)
        self.value = False
        self.stop()


class Context(commands.Context):

    async def get_verification(self, ctx, *args, **kwargs) -> bool:
        view = Confirm()
        kwargs['view'] = view
        await ctx.send(*args, **kwargs)
        await view.wait()
        
        if not view.value:
            return False
        return True
    