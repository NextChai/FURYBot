import discord
from discord.ext import commands

from typing import Optional


class Owner(commands.Cog):
    """Owner commands for the bot. Basically manage it"""
    def __init__(self, bot):
        self.bot = bot
    
    @commands.slash()
    @commands.has_permissions(manage_channels=True)
    async def createteam(
        self, 
        ctx: commands.Context, 
        team_name: str,
        mem1: discord.Member,
        mem2: discord.Member,
        mem3: discord.Member,
        mem4: Optional[discord.Member],
        mem5: Optional[discord.Member],
        mem6: Optional[discord.Member],
    ) -> None:
        members = [m for m in ctx.args if isinstance(m, discord.Member)]
        overwrites = {m: discord.PermissionOverwrite(connect=True, send_messages=True, view_channel=True) for m in members}
        overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(connect=False, send_messages=False, view_channel=False)
        
        
        category = await ctx.guild.create_category(team_name)
        text = await category.create_text_channel(team_name.replace(' ', '-'), overwrites=overwrites)
        voice = await category.create_voice_channel(f'{team_name} Voice', overwrites=overwrites)

        embed = discord.Embed(
            title='Done!',
            description=f'Created a category called {category.mention}, a text chanel called {text.mention}, and a voice channel called {voice.mention}')
        return await ctx.send(embed=embed)
        

    
def setup(bot):
    bot.add_cog(Owner(bot))