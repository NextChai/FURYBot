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

import re
import copy
import logging
from fuzzywuzzy import process
from numpydoc.docscrape import (
    NumpyDocString as process_doc,
    Parameter
)
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Mapping,
    Optional,
)

from bot import Embed
from utils.context import Context
from .time import human_join

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from bot import FuryBot
    from . import BaseCog
    from .context import Context

log = logging.getLogger(__name__)
    
CORO_REGEX = re.compile(r'\|[a-z]+\|', flags=re.IGNORECASE)

def _find_bot(finder: Any) -> FuryBot:
    if hasattr(finder, '__is_fury_bot__'):
        return finder 
    
    bot: Optional[FuryBot] = None
    parent = finder
    while not bot:
        bot = getattr(parent, 'bot')
        if bot:
            break
        
        parent = getattr(finder, 'parent', None)
        if not parent:
            raise RuntimeError('Could not find bot.')
        
    if bot is None:
        raise TypeError('Could not find bot attribute')
    
    return bot

def _parse_command_doc(command: commands.Command, embed: discord.Embed) -> discord.Embed:
    help_doc = command.help
    if not help_doc:
        return embed
    
    for found in CORO_REGEX.findall(help_doc):
        help_doc = help_doc.replace(found, '')
    
    processed = process_doc(help_doc)
    for name, value in processed._parsed_data.items():
        if not value or (isinstance(value, list) and not value[0]) or value == '':
            continue
        
        if isinstance(value, list) and isinstance(value[0], Parameter):
            fmt = []
            for item in value:
                fmt.append('`{0}`: {1}'.format(item.name, ' '.join(item.desc)))
            
            value = '\n\n'.join(fmt)
        elif isinstance(value, list):            
            value = ' '.join(value)
            
        embed.add_field(name=name, value=value, inline=False)
    
    return embed


class GoHome(discord.ui.Button):
    def __init__(self, parent: Any) -> None:
        super().__init__(label='Go Home')
        
        self.bot: FuryBot = _find_bot(parent)
        
        home = None
        if not isinstance(parent, HomeView) and self.bot != parent:
            while hasattr(parent, 'parent'):
                parent = parent.parent
                if isinstance(parent, HomeView):
                    home = parent
                    break
        else:
            home = parent
        
        self.home: Optional[HomeView] = home
        
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.home:
            return await interaction.response.edit_message(embed=self.home.embed, view=self.home)
        
        help_command = self.bot.help_command
        if not help_command:
            raise RuntimeError('Help command is not enabled')
        
        mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
        self.home = view = HomeView(self.bot, mapping) # type: ignore
        return await interaction.response.edit_message(embed=view.embed, view=view)
    

class GoBack(discord.ui.Button):
    def __init__(self, parent: Any) -> None:
        super().__init__(label='Go Back')
        self.parent: Any = parent
        self.bot: FuryBot = _find_bot(parent)
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.parent != self.bot:
            return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)
        
        mapping = {cog: cog.get_commands() for cog in self.bot.cogs.values()}
        home = HomeView(self.bot, mapping) # type: ignore
        home.bot = self.bot
        
        return await interaction.response.edit_message(embed=home.embed, view=home)
    
class Stop(discord.ui.Button):
    def __init__(self, parent: discord.ui.View) -> None:
        super().__init__(label='Stop', style=discord.ButtonStyle.red)
        self.parent: discord.ui.View = parent
    
    async def callback(self, interaction: discord.Interaction) -> None:
        for child in self.parent.children:
            child.disabled = True # type: ignore
        
        await interaction.response.edit_message(view=self.parent)
        self.parent.stop()
             
        
class CommandView(discord.ui.View):
    def __init__(self, parent: Any, command: commands.Command) -> None:
        super().__init__()
        self.bot: FuryBot = _find_bot(parent)
        self.command: commands.Command = command
        self.parent: Any = parent
        
        self.add_item(GoBack(parent))
        self.add_item(GoHome(self))
        self.add_item(Stop(self))
    
    @discord.utils.cached_property
    def embed(self) -> discord.Embed:
        embed = Embed(title=self.command.qualified_name, description=f'How to use this command: `fury.{self.command.qualified_name} {self.command.signature}`')
        _parse_command_doc(self.command, embed)
        return embed


class CommandSelect(discord.ui.Select):
    def __init__(self, parent: Any, commands: List[commands.Command]) -> None:
        super().__init__(
            placeholder='Select a command...',
            options=[
                discord.SelectOption(label=command.qualified_name, value=command.qualified_name) for command in commands
            ]
        )
        
        self.command_mapping: Dict[str, commands.Command] = {command.qualified_name: command for command in commands}
        self.bot: FuryBot = _find_bot(parent)
        self.parent: Any = parent
        
    async def callback(self, interaction: discord.Interaction) -> None:
        # Get command view here
        command = self.command_mapping[self.values[0]]
        view = CommandView(self.parent, command)
        await interaction.response.edit_message(embed=view.embed, view=view)


class GroupView(discord.ui.View):
    def __init__(self, parent: Any, group: commands.Group) -> None:
        super().__init__()
        self.bot: FuryBot = _find_bot(parent)
        self.parent: Any = parent
        self.group: commands.Group = group
        
        self.add_item(CommandSelect(self, list(group.commands)))
        self.add_item(Stop(self))
    
    @discord.utils.cached_property
    def embed(self) -> discord.Embed:
        embed = Embed(title=self.group.qualified_name, description=f'How to use this command: `fury.{self.group.qualified_name} {self.group.signature}`')
        _parse_command_doc(self.group, embed)
        embed.add_field(name='Subcommands', value=human_join([f'`{c.qualified_name}`' for c in self.group.commands]))
        return embed
        

# Cog view, will show help for a cog 
class CogView(discord.ui.View):
    def __init__(self, parent: Any, cog: BaseCog) -> None:
        super().__init__()
        self.cog: BaseCog = cog
        self.parent: Any = parent
        self.bot: FuryBot = _find_bot(parent)
        
        self.add_item(CommandSelect(self, list(cog.get_commands())))
        self.add_item(GoBack(parent))
        self.add_item(GoHome(self))
        self.add_item(Stop(self))
    
    @discord.utils.cached_property
    def embed(self) -> discord.Embed:
        new = Embed(
            title=f'{self.cog.emoji if self.cog.emoji else ""}{self.cog.qualified_name}',
            description=self.cog.description,
        )
        
        commands = self.cog.get_commands()
        cmd_fmt = human_join([f'`{c.qualified_name}`' for c in commands])
        new.add_field(name='Commands', value=f'There are {len(commands)} commands in this group, select one in the dropdown menu to learn a bit more about it.\n\n{cmd_fmt}')
        
        return new

# Cog selection select menu
class HomeViewSelect(discord.ui.Select):
    def __init__(self, parent: Any, cogs: List[BaseCog]):
        super().__init__(
            placeholder='Select a category',
            options=[
                discord.SelectOption(label=cog.qualified_name, value=cog.qualified_name, emoji=cog.emoji) for cog in cogs
            ]
        )
        self.bot: FuryBot = _find_bot(parent)
        self.parent: Any = parent
        self.cog_mapping = {cog.qualified_name: cog for cog in cogs}
    
    async def callback(self, interaction: discord.Interaction) -> None:
        selected_cog = self.cog_mapping[self.values[0]]
        view = CogView(self.parent, selected_cog)
        return await interaction.response.edit_message(embed=view.embed, view=view)


# Main home view, allows you to select cogs
class HomeView(discord.ui.View):
    def __init__(self, parent: Any, mapping: Mapping[Optional[BaseCog], List[commands.Command]]) -> None:
        super().__init__()
        self.bot: FuryBot = _find_bot(parent)
        
        clean_cogs = [c for c in mapping.keys() if c]
        self.add_item(HomeViewSelect(self.bot, clean_cogs))
        self.add_item(Stop(self))
    
    @discord.utils.cached_property
    def embed(self) -> discord.Embed:
        embed = Embed(
            title='FuryBot Help',
            description='FuryBot is a Discord bot that is designed to be a moderation tool for the FLVS Fury Administrators '
                        'to use. It does many things, such as moderation, logging, and more.\n\n'
                        'Use "fury.help command" for help on a command.\n'
                        'Use "fury.help category" for help on a category.\n'
        )
        embed.add_field(name='Open Source!', value='I am [open source](https://github.com/NextChai/Fury-Bot), feel free to check out my source code.')
        return embed


class FuryHelp(commands.HelpCommand[Context]):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, verify_checks=True)
        
    @property
    def bot(self) -> FuryBot:
        if (bot := getattr(self, '_bot', None)):
            return bot
        
        return self.context.bot
    
    @bot.setter
    def bot(self, new: FuryBot) -> None:
        self._bot = new
        
    async def _filter_mapping(self, mapping: Mapping[Optional[BaseCog], List[commands.Command]]) -> Mapping[Optional[BaseCog], List[commands.Command]]:
        commands = sum(mapping.values(), [])
        await self.filter_commands(commands)
        
        cogs = {}
        for command in commands:
            key = command.cog
            if key not in cogs:
                cogs[key] = [command]
            else:
                cogs[key].append(command)
        
        return cogs
    
    async def send_bot_help(self, mapping: Mapping[Optional[BaseCog], List[commands.Command]]) -> discord.Message:
        mapping = await self._filter_mapping(mapping)
        view = HomeView(self.bot, mapping)
        return await self.context.send(embed=view.embed, view=view)
    
    async def send_cog_help(self, cog: BaseCog, /) -> discord.Message:
        
        keep_commands = [c for c in cog.__cog_commands__ if c.parent]
        filtered = await self.filter_commands(cog.get_commands())
        
        new_cog = copy.copy(cog)
        new_cog.__cog_commands__ = keep_commands + filtered
        
        view = CogView(self.bot, new_cog)
        return await self.context.send(embed=view.embed, view=view)

    async def send_group_help(self, group: commands.Group[Any, ..., Any], /) -> discord.Message:
        view = GroupView(self.bot, group)
        return await self.context.send(embed=view.embed, view=view)
    
    async def send_command_help(self, command: commands.Command[Any, ..., Any], /) -> discord.Message:
        view = CommandView(self.bot, command)
        return await self.context.send(embed=view.embed, view=view) 
    
    async def command_not_found(self, string: str, /) -> str:
        maybe_found = await self.bot.wrap(process.extractOne, string, [c.qualified_name for c in self.bot.commands])
        return f'The command called "{string}" was not found. Maybe you meant `{self.context.prefix}{maybe_found[0]}`?'
    
    async def subcommand_not_found(self, command: commands.Command[Any, ..., Any], string: str, /) -> str:
        fmt = [f'There was no subcommand named "{string}" found on that command.']
        if isinstance(command, commands.Group):
            maybe_found = await self.bot.wrap(process.extractOne, string, [c.qualified_name for c in command.commands])
            fmt.append(f'Maybe you meant `{maybe_found[0]}`?')
        
        return ''.join(fmt)
    
    async def on_help_command_error(self, ctx: Context, error: commands.CommandError, /) -> None:
        await ctx.send('I ran into a new error! I apologize for the inconvenience.')
        
        log.warning('New error in help command', exc_info=error)
    

async def setup(bot: FuryBot) -> None:
    bot.help_command = FuryHelp()

async def teardown(bot: FuryBot) -> None:
    bot.help_command = commands.MinimalHelpCommand()