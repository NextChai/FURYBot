import discord
from discord.ext import commands

import inspect, os, time



class Commands(commands.Cog):
    """General commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Ping the bot.")
    async def ping(self, ctx):
        await ctx.send("Pong.")
        
    @commands.command(brief="Get the recent changes to the bot!")
    async def changes(self, ctx):
        embed = discord.Embed(color=discord.Color.blue(), description='')
        
        commits = await self.bot.get_recent_commits()
        for commit in commits:
            embed.description += f'```python\nSummary: {commit.summary}\nAuthorized: {time.strftime("%a, %d %b %Y %H:%M", time.gmtime(commit.committed_date))}```'
        return await ctx.send(embed=embed)
        
    @commands.command(brief="View the source code for the bot.")
    async def source(self, ctx, command: str = None):
        """Source command taken from R.Danny.
        
        Check out the original command here: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L344-L382
        And check out the bot here: https://github.com/Rapptz/RoboDanny/
        
        The bot owner does not claim the rights or originality to this command, 
        and is in guidance with the [Liscense](https://github.com/Rapptz/RoboDanny/blob/rewrite/LICENSE.txt) put into effect from the R.Danny bot owner."""
        
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

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)
    
def setup(bot):
    bot.add_cog(Commands(bot))