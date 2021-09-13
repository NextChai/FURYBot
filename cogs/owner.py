import discord
from discord.ext import commands

import sys
import importlib
import re
import os
import traceback
import asyncio
import subprocess
import aiofile

from typing import Optional


class Owner(commands.Cog):
    """Owner commands for the bot. Basically manage it"""
    def __init__(self, bot):
        self.bot = bot
        self._GIT_PULL_REGEX = re.compile(r'\s*(?P<filename>.+?)\s*\|\s*[0-9]+\s*[+-]+')
        
    async def run_process(self, command):
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]
    
    def find_modules_from_git(self, output):
        files = self._GIT_PULL_REGEX.findall(output)
        ret = []
        for file in files:
            root, ext = os.path.splitext(file)
            if ext != '.py':
                continue

            if root.startswith('cogs/'):
                # A submodule is a directory inside the main cog directory for
                # my purposes
                ret.append((root.count('/') - 1, root.replace('/', '.')))

        # For reload order, the submodules should be reloaded first
        ret.sort(reverse=True)
        return ret
    
    def reload_or_load_extension(self, module):
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionNotLoaded:
            self.bot.load_extension(module)
        
    @commands.slash(description='Git pull to update the bot.')
    @commands.has_permissions(kick_members=True)
    async def pull(self, ctx):
        async with ctx.typing():
            stdout, stderr = await self.run_process('git pull')
            
        if stdout.startswith('Already up-to-date.'):
            return await ctx.send(stdout)
        
        modules = self.find_modules_from_git(stdout)
        mods_text = '\n'.join(f'{index}. `{module}`' for index, (_, module) in enumerate(modules, start=1))
        prompt_text = f'This will update the following modules, are you sure?\n{mods_text}'
        confirm = await ctx.prompt(prompt_text, reacquire=False)
        if not confirm:
            return await ctx.send('Aborting.')
        
        statuses = []
        for is_submodule, module in modules:
            if is_submodule:
                try:
                    actual_module = sys.modules[module]
                except KeyError:
                    statuses.append((ctx.tick(None), module))
                else:
                    try:
                        importlib.reload(actual_module)
                    except Exception as e:
                        statuses.append((ctx.tick(False), module))
                    else:
                        statuses.append((ctx.tick(True), module))
            else:
                try:
                    self.reload_or_load_extension(module)
                except commands.ExtensionError:
                    statuses.append((ctx.tick(False), module))
                else:
                    statuses.append((ctx.tick(True), module))

        await ctx.send('\n'.join(f'{status}: `{module}`' for status, module in statuses))
        
    @commands.group()
    async def extension(self):
        pass
        
    @extension.slash()
    @commands.has_permissions(manage_channels=True)
    async def reload(self, ctx, extension: str) -> None:
        try:
            self.bot.reload_extension(extension)
        except Exception as exc:
            trace = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
            lines = f'Ignoring exception in command {ctx.command}:\n```py\n{trace}```'
            return await ctx.send(lines)
        return await ctx.send(f'Reloaded {extension} sucessfully.')
    
    @extension.slash()
    @commands.has_permissions(manage_channels=True)
    async def unload(self, ctx, extension: str) -> None:
        try:
            self.bot.unload_extension(extension)
        except Exception as exc:
            trace = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
            lines = f'Ignoring exception in command {ctx.command.name}:\n```py\n{trace}```'
            return await ctx.send(lines)
        return await ctx.send(f'Unloaded {extension} sucessfully.')
    
    @extension.slash()
    @commands.has_permissions(manage_channels=True)
    async def load(self, ctx, extension: str) -> None:
        try:
            self.bot.load_extension(extension)
        except Exception as exc:
            trace = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
            lines = f'Ignoring exception in command {ctx.command.name}:\n```py\n{trace}```'
            return await ctx.send(lines)
        return await ctx.send(f'Loaded {extension} sucessfully.')
        
    
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
    async def whitelist(self):
        pass
    
    @whitelist.slash()
    @commands.has_permissions(manage_channels=True)
    async def add(self, ctx, word: str) -> None:
        async with aiofile.async_open('txt/profanity.txt', 'a') as f:
            await f.write(f'\n{word}')
        return await ctx.send(f"Added {word} to the whitelist.", ephemeral=True)
    
    @whitelist.slash()
    @commands.has_permissions(manage_channels=True)
    async def remove(self, ctx, word: str) -> None:
        async with aiofile.async_open('txt/profanity.txt', 'r') as f:
            data = await f.read()
            words = [w.replace('\n', '') for w in data]
        
        to_remove = [w for w in words if w == word]
        cleaned = [w for w in words if w not in to_remove]
        async with aiofile.async_open('txt/profanity.txt', 'w') as f:
            await f.write('\n'.join(cleaned))  
        
        return await ctx.send(f"Removed {to_remove} from the whitelist.")            
    
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