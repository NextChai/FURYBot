import discord
from discord.ext import commands

from typing import Optional

class ConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: float, author_id: int, reacquire: bool, ctx, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.ctx: Context = ctx
        self.reacquire: bool = reacquire
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message('This confirmation dialog is not for you.', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        if self.reacquire:
            await self.ctx.acquire()
        if self.delete_after and self.message:
            await self.message.delete()

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

class Context(commands.Context):
    
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

    async def prompt(
        self,
        message: str,
        *,
        timeout: float = 60.0,
        delete_after: bool = True,
        reacquire: bool = True,
        author_id: Optional[int] = None,
    ) -> Optional[bool]:
        author_id = author_id or self.author.id
        view = ConfirmationView(
            timeout=timeout,
            delete_after=delete_after,
            reacquire=reacquire,
            ctx=self,
            author_id=author_id, # type: ignore
        )
        view.message = await self.send(message, view=view)
        await view.wait()
        return view.value
    
    