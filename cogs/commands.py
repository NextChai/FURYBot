import discord
from discord.ext import commands



class Commands(commands.Cog):
    """General commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Ping the bot.")
    async def ping(self, ctx):
        await ctx.send("Pong.")
        
    @commands.command(brief="View the source code for the bot.")
    async def source(self, ctx):
        embed = discord.Embed(color=discord.Color.blue(), description=f'https://github.com/NextChai/FURYBot')
        return await ctx.send(embed=embed)
    
    
def setup(bot):
    bot.add_cog(Commands(bot))