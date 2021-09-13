import discord
from discord.ext import commands

import aiofile

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
    
    @commands.group()
    async def filter(self):
        pass
    
    @filter.command()
    @commands.has_permissions(manage_channels=True)
    async def add(self, ctx, word: str) -> None:
        async with aiofile.async_open('txt/profanity.txt', 'a') as f:
            await f.write(f'\n{word}')
        return await ctx.send("Added {word} to the whitelist.", empheral=True)
    
    @filter.command()
    @commands.has_permissions(manage_channels=True)
    async def remove(self, ctx, word: str) -> None:
        async with aiofile.async_open('txt/profanity.txt', 'r') as f:
            data = await f.read()
            words = [w.replace('\n', '') for w in data]
        
        cleaned = [w for w in words if w.lower() != word.lower()]
        async with aiofile.async_open('txt/profanity.txt', 'w') as f:
            await f.write('\n'.join(cleaned))  
        
        return await ctx.send(f"Removed {word} from the whitelist.")            
    
    @commands.slash()
    @commands.is_owner()
    async def contains_profanity(self, ctx, message: str):
        return await ctx.send(str(self.bot.profanity.contains_profanity(message)))
    
    @commands.slash()
    @commands.is_owner()
    async def censor(self, ctx, message: str):
        return await ctx.send(str(self.bot.profanity.censor(message)))
    
def setup(bot):
    bot.add_cog(Owner(bot))