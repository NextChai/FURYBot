import discord
from discord.ext import commands
import git
import re
import logging



def update_files(default_base_path: str):
    change = git.cmd.Git(default_base_path).pull('https://github.com/NextChai/FURYBot','main')
    return change
    
    
class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Reset the errors found inside of the bot.")
    @commands.is_owner()
    async def reset_errors(self, ctx):
        if not hasattr(self.bot, "command_errors"):
            return await ctx.send("command_errors has not been set yet, you're all good.")
        
        self.bot.command_errors = {}
        return await ctx.send("command_errors has been reset, you're all good to go.")
    
    @commands.command(brief="Need to update the bot? Use this command.")
    @commands.is_owner()
    async def sync(self, ctx):
        change = update_files(self.bot.DEFAULT_BASE_PATH)
        logging.info(change)
        
        files_to_update = re.findall(r'cogs/.*.py', change)
        if not files_to_update:  # already up to date
            return await ctx.send(embed=discord.Embed(color=discord.Color.blue(), description=change))
        
        files_to_update = [file.replace("/", '.') for file in files_to_update]
        self.bot.dispatch("on_handle_update", files_to_update, ctx.channel)
        
    

    
def setup(bot):
    bot.add_cog(Owner(bot))