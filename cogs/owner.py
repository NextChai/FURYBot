import logging
import re

import discord
from discord.ext import commands


class Owner(commands.Cog):
    """Owner commands for the bot. Basically manage it"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Reset the errors found inside of the bot.")
    @commands.is_owner()
    async def reset_errors(self, ctx):
        if not hasattr(self.bot, "command_errors"):
            return await ctx.send("command_errors has not been set yet, you're all good.")
        
        self.bot.command_errors = {}
        return await ctx.send("command_errors has been reset, you're all good to go.")
    
    @commands.command(brief="See any errors found inside of the bot.")
    @commands.is_owner()
    async def errors(self, ctx):
        if not hasattr(self.bot, 'command_errors'):
            return await ctx.send("No errors to show.")
        
        errors = []
        for command in self.bot.command_errrors:
            command = self.bot.command_errors[command]
            if command.get("count") > 0 :
                errors.append(command)
            
        if not errors:
            return await ctx.send("No errors to show.") # this technically can't happen, but its chill
        
        e = discord.Embed(color=discord.Color.blue())
        for error in errors:
            jumps = ', '.join(error.get('jump'))
            e.add_field(name=error.get('name'), value=f"**Count:** {error.get('count')}\nJump: {jumps}\nTraceback: {error.get('traceback')[0]}")
        await ctx.send(embed=e)
    
    @commands.command(brief="Need to update the bot? Use this command. ")
    @commands.is_owner()
    async def sync(self, ctx):
        change = await self.bot.sync()
        logging.info(change)
        
        files_to_update = re.findall(r'cogs/.*.py', change)
        if not files_to_update:  # already up to date
            return await ctx.send(embed=discord.Embed(color=discord.Color.blue(), description=change))
        
        files_to_update = [file.replace("/", '.').replace(".py", "") for file in files_to_update if "utils" not in file]
        self.bot.dispatch("handle_update", files_to_update, ctx.channel, change)
        
    

    
def setup(bot):
    bot.add_cog(Owner(bot))