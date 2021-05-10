import discord
from discord.ext import commands

import inspect, os



class Commands(commands.Cog):
    """General commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Ping the bot.")
    async def ping(self, ctx):
        await ctx.send("Pong.")
        
    @commands.command(brief="View the source code for the bot.")
    async def source(self, ctx, command: str = None):
        """Source command taken from R.Danny.
        
        Check out the origional command here: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L344-L382
        And check out the bot here: https://github.com/Rapptz/RoboDanny/
        
        I do not claim the rights to this command, and is in guidance with the [Liscense](https://github.com/Rapptz/RoboDanny/blob/rewrite/LICENSE.txt) put into effect.
        
        
        Such Covered Software must also be made available in Source Code
        Form, as described in Section 3.1, and You must inform recipients of
        the Executable Form how they can obtain a copy of such Source Code
        Form by reasonable means in a timely manner, at a charge no more
        than the cost of distribution to the recipient; and

        You may distribute such Executable Form under the terms of this
        License, or sublicense it under different terms, provided that the
        license for the Executable Form does not attempt to limit or alter
        the recipients' rights in the Source Code Form under this License."""
        
        source_url = 'https://github.com/NextChai/FURYBot'
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