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
        
    @commands.command(aliases=['clear'])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, limit: Optional[int], oldest_first: Optional[bool] = False):
        async for message in ctx.channel.history(limit=limit, oldest_first=oldest_first):
            await message.delete()
    
    
    @commands.command(
        brief="Ping the bot.")
    async def ping(
        self, 
        ctx: commands.Context
    ) -> discord.Message:
        return await ctx.send("Pong.")
        
    @commands.command(
        brief="Get the recent changes to the bot!")
    async def changes(
        self, 
        ctx: commands.Context
    ) -> discord.Message:
        embed = self.bot.Embed(color=discord.Color.blue(), description='')
        
        commits = await self.bot.get_recent_commits()
        for commit in commits:
            embed.description += f'```python\nSummary: {commit.summary}\nAuthorized: {time.strftime("%a, %d %b %Y %H:%M", time.gmtime(commit.committed_date))} ({commit.author})```'
        return await ctx.send(embed=embed)
        
    @commands.command(
        brief="View the source code for the bot.")
    async def source(
        self, 
        ctx: commands.Context, 
        *,
        command: Optional[str] = None
    ) -> discord.Message:
        """
        Source command taken from R.Danny.
        
        Check out the original command here: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L344-L382
        And check out the bot here: https://github.com/Rapptz/RoboDanny/
        
        The bot owner does not claim the rights or originality to this command, 
        and is in guidance with the [License](https://github.com/Rapptz/RoboDanny/blob/rewrite/LICENSE.txt) put into effect from the R.Danny bot owner.
        """
        
        source_url = '<https://github.com/NextChai/FURYBot>'
        branch = "main"
        if not command:
            return await ctx.send(source_url)
    
        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
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
