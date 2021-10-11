"""
The MIT License (MIT)

Copyright (c) 2020-present NextChai

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import io
import os
import re
import sys
import asyncio
import textwrap
import subprocess
import traceback
import importlib
from contextlib import redirect_stdout
from typing import TYPE_CHECKING, List

import discord
from discord.ext import commands

from cogs.utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot
    


__all__ = (
    'Owner',
)


class Owner(commands.Cog):
    """The Owner cog for the bot. All commands inside of this cog are owner specific,
    meaning all commands are limited to the owner of the bot.
    
    Attributes
    ----------
    bot: :class:`FuryBot`
        The main bot client.
    _GIT_PULL_REGEX: :class:`re.Pattern`
        Used to find cogs in a git pull resp.
    """
    def __init__(self, bot):
        self.bot: FuryBot = bot
        self._GIT_PULL_REGEX: re.Pattern = re.compile(r'\s*(?P<filename>.+?)\s*\|\s*[0-9]+\s*[+-]+')
        
    async def cog_check(self, ctx: Context):
        """A blanket cog check limiting all commands to the Owner of the bot.
        
        Parameters
        ----------
        ctx: :class:`Context`
            The invoke context for the command.
        """
        if not (await self.bot.is_owner(ctx.author)):
            raise commands.NotOwner('You do not own this bot.')
        return True
        
    async def run_process(self, command: str) -> List:
        """Used to run a command via subprocess.
        
        Parameters
        ----------
        command: :class:`str`
            The command to run.
        
        Returns
        -------
        List
        """
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await process.communicate()
        except NotImplementedError:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = await self.bot.loop.run_in_executor(None, process.communicate)

        return [output.decode() for output in result]
        
    def find_modules_from_git(self, output: str) -> List[str]:
        """Used to find modules from a git pull resp.
        
        Parameters
        ---------
        output: :class:`str`
            The output from the `git pull` command.
        
        Returns
        -------
        List[:class:`str`]
            Any modules found to reload.
        """
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

    def reload_or_load_extension(self, module: str) -> None:
        """Used to reload or load the extension given.
        
        Parameters
        ----------
        module: :class:`str`
            The module to reload or load.
        
        Returns
        -------
        None
        """
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionNotLoaded:
            self.bot.load_extension(module)
            
    @commands.group(name='git', description='Handle git interactions.')
    @commands.is_owner()
    async def git(self) -> None:
        """A command group to use and manage git interactions.
        
        
        Subcommands
        -----------
        pull: `/git pull`
            A simple command used to pull from the repo and recieve updates.
        """
        pass
    
    @git.slash(
        name='pull',
        description='Pull from the github to update the bot'
    )
    async def git_pull(self, ctx: Context) -> None:
        async with ctx.typing():
            stdout, stderr = await self.run_process('git pull')

        # progress and stuff is redirected to stderr in git pull
        # however, things like "fast forward" and files
        # along with the text "already up-to-date" are in stdout

        if stdout.lower().startswith('already'):
            return await ctx.send(stdout)

        modules = self.find_modules_from_git(stdout)
        mods_text = '\n'.join(f'{index}. `{module}`' for index, (_, module) in enumerate(modules, start=1))
        prompt_text = f'This will update the following modules, are you sure?\n{mods_text}'
        confirm = await ctx.get_confirmation(prompt_text)
        if not confirm:
            return await ctx.interaction.delete_original_message()

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
        
        
    @commands.slash(
        name='debug',
        description='Toggle the debug feature of the bot.',
        options=[
            commands.CommandOption(
                'enabled',
                'To enable or disable debug',
                type=commands.OptionType.string,
                choices=[
                    commands.CommandOptionChoice(name='Enabled', value='true'),
                    commands.CommandOptionChoice(name='Disabled', value='false')
                ]
            )
        ]
    )
    @commands.is_owner()
    async def debug(self, ctx: Context, enable: str):
        converter = {
            'true': True,
            'false': False
        }
        self.bot.debug = converter[enable]
        
        e = self.bot.Embed(
            title='Success!',
            description='The bots debug has been toggled.'
        )
        return await ctx.send(embed=e)
    
    @commands.slash(
        name='python',
        description='Run code.',
        options=[
            commands.CommandOption('code', 'The code to evaluate', required=True)
        ]
    )
    @commands.is_owner()
    async def python(self, ctx: Context, code: str):
        globalns = {
            'ctx': ctx,
            'guild': ctx.guild,
            'author': ctx.author,
            'discord': discord,
            'utils': discord.utils,
            'bot': ctx.bot,
        }
        
        globalns.update(globals())
        
        stdout = io.StringIO()
        code = code.replace('```python', '```').replace('```', '')
        to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'
        
        try:
            exec(to_compile, globalns)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')
        
        func = globalns['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{ret}\n```')
                
def setup(bot):
    bot.add_cog(Owner(bot))