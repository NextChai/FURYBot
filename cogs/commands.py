import discord
from discord.ext import commands



class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Ping the bot.")
    async def ping(self, ctx):
        await ctx.send("Pong.")
    
    
def setup(bot):
    bot.add_cog(Commands(bot))