import discord
from discord.ext import commands


class Owner(commands.Cog):
    """Owner commands for the bot. Basically manage it"""
    def __init__(self, bot):
        self.bot = bot
    
    # Note: nothing here yet due to new update
    

    
def setup(bot):
    bot.add_cog(Owner(bot))