import os
import time
import inspect

import discord
from discord.ext import commands

from typing import Optional


class Commands(commands.Cog):
    """General commands"""
    def __init__(self, bot):
        self.bot = bot
        
    @commands.slash()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, limit: Optional[int] = 0, oldest_first: Optional[bool] = False):
        async for message in ctx.channel.history(limit=limit, oldest_first=oldest_first):
            try:
                await message.delete()
            except:
                continue
    
    @commands.slash()
    async def ping(self, ctx: commands.Context) -> discord.Message:
        """Ping the bot"""
        return await ctx.send("Pong.")
        
    @commands.slash()
    async def source(self, ctx: commands.Context, command: Optional[str] = None) -> None:
        """View the Source code for the bot."""
        
        source_url = '<https://github.com/NextChai/FURYBot>'
        branch = "main"
        if not command:
            return await ctx.send(source_url)
    
        obj = self.bot.get_command(command.replace('.', ' '))
        if obj is None:
            return await ctx.send('Could not find command.')

        # since we found the command we're looking for, presumably anyway, let's
        # try to access the code itself
        src = obj.callback.__code__
        module = obj.callback.__module__
        filename = src.co_filename

        lines, first_line = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{first_line}-L{first_line + len(lines) - 1}>'
        await ctx.send(final_url)


def setup(bot):
    bot.add_cog(Commands(bot))
