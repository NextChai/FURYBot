import discord
from discord.ext import commands


class Owner(commands.Cog):
    """Owner commands for the bot. Basically manage it"""
    def __init__(self, bot):
        self.bot = bot
    
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
        
    @commands.command(brief="Reset the errors found inside of the bot.")
    @commands.is_owner()
    async def reset_errors(self, ctx):
        if not hasattr(self.bot, "command_errors"):
            return await ctx.send("command_errors has not been set yet, you're all good.")
        
        self.bot.command_errors = {}
        return await ctx.send("command_errors has been reset, you're all good to go.")
    

    
def setup(bot):
    bot.add_cog(Owner(bot))