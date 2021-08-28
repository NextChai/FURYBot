import traceback
from typing import List, Any, Union

import discord
from discord.ext import commands

def get_command_signature(command):
    parent = command.full_parent_name
    if len(command.aliases) > 0:
        aliases = ", ".join(command.aliases)
        name = f'[{command.name} | [{aliases}]'
        if parent:
            name = f'{parent} {name}'
        alias = name
    else:
        alias = command.name if not parent else f'{parent} {command.name}'
    return f'{alias} {command.signature}'

class InviteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='Invite Chai!',
            style=discord.ButtonStyle.blurple, 
            url='https://discord.com/oauth2/authorize?client_id=728115804826239017&scope=bot&permissions=422964311'
        )

class BaseButtonPage(discord.ui.View):
    __slots__ = ('entries', 'per_page', 'ctx', '_max_page', '_min_page', '_current_page', 'pages')
    
    def __init__(
        self, 
        entries: List[Any], 
        *, 
        author: Union[discord.Member, discord.User], 
        per_page: int = 6,
        want_invite_link: bool = True
    ) -> None:
        super().__init__(timeout=180)
        self.entries = entries
        self.per_page = per_page
        self.ctx = None
        self.author = author
        
        pages, left_over = divmod(len(entries), per_page)
        if left_over:
            pages += 1
            
        self._max_page = pages
        self._min_page = 1
        self._current_page = 1
        self.pages = list(self._format_pages(entries, self.per_page))
        
        if self._max_page <= 1:
            self.clear_items()
        else:
            if want_invite_link:
                self.add_item(InviteButton())
            
    async def format_page(self, entries) -> None:
        return None
    
    def _format_pages(self, entries, per_page):
        for i in range(0, len(entries), per_page):
            yield entries[i:i + per_page]
            
    def _get_entries(self, *, up: bool = True, increment: bool = True):
        if increment:
            if up:
                self._current_page += 1
                if self._current_page > self._max_page:
                    self._current_page = self._min_page     
            else:
                self._current_page -= 1
                if self._current_page < self._min_page:
                    self._current_page = self._max_page
                    
        return self.pages[self._current_page - 1]
    
    @discord.ui.button(emoji='\U000025c0', style=discord.ButtonStyle.blurple)
    async def on_arrow_backward(self, button, interaction):
        entries = self._get_entries(up=False)
        embed = await self.format_page(entries=entries)
        return await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(emoji='\U000025b6', style=discord.ButtonStyle.blurple)
    async def on_arrow_forward(self, button, interaction):
        entries = self._get_entries(up=True)
        embed = await self.format_page(entries=entries)
        return await interaction.response.edit_message(embed=embed)
    
    @discord.ui.button(emoji='\U000023f9', style=discord.ButtonStyle.blurple)
    async def on_stop(self, button, interaction):
        self.clear_items()
        self.stop()
        return await interaction.response.edit_message(view=self)
    
    async def on_error(self, error: Exception, item, interaction: discord.Interaction) -> discord.Message:
        traceback_str = ''.join(traceback.format_exception(error.__class__, error, error.__traceback__))
        await self.bot.send_to_owner(traceback_str)
        return await interaction.response.send_message('I ran into an error with this!')
    
    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id
    
    async def start(self, context):
        self.ctx = context
        
        entries = self._get_entries(increment=False)
        embed = await self.format_page(entries=entries)
        await context.send(embed=embed, view=self)
        

class BaseMenu(BaseButtonPage):
    def __init__(self, entries: List[Any], *, author: Union[discord.Member, discord.User], per_page: int = 6):
        super().__init__(entries, per_page=per_page, author=author, want_invite_link=False)
        
    async def format_page(self, entries: List[Any]):
        return None


class DefaultHelp(BaseButtonPage):
    __slots__ = ('embed', 'total_commands')
    
    def __init__(self, entries, *, author, embed) -> None:
        super().__init__(entries, per_page=6, author=author)
        self.embed = embed
        
        total_commands = 0
        for entry in entries:
            total_commands += len(entry)
        self.total_commands = total_commands
    
    async def format_page(self, entries: List[List[Any]]) -> discord.Embed:
        e = self.embed(
            title='Categories',
            description='Use "chai + command" for more info on a command.\n' \
                'Use "chai + category" for more info on a category.\n' \
                f'For more help, join the Chai support server: https://discord.gg/hCMtFkG'
        )
        e.set_footer(text=f'Page {self._current_page} / {self._max_page} :: {self.total_commands} commands total.')
        for commands in entries:
            cog = commands[0].cog
            name = cog.qualified_name
            formatted = [f'`{command.name}`' for command in commands]
            value = '{}\n{}'.format(cog.description, ', '.join(formatted))
            e.add_field(name=name, value=value)
        
        return e
    
class CogHelp(BaseButtonPage):
    __slots__ = ('embed')
    
    def __init__(self, entries, *, author, embed) -> None:
        super().__init__(entries, per_page=6, author=author)
        self.embed = embed
        
    async def format_page(self, entries) -> discord.Embed:
        cog = entries[0].cog
        e = self.embed(title=cog.qualified_name, description=cog.description)
        e.set_footer(text='Use "chaihelp + command" for more info on a command.')
        for command in entries:
            e.add_field(name=f'{command.name} {command.signature}', value=command.brief or "No brief given..", inline=False)
        return e
     
class GroupHelp(BaseButtonPage):
    __slots__ = ('embed', 'extra')
    
    def __init__(self, entries, *, author, embed, extra):
        super().__init__(entries, per_page=6, author=author)
        self.embed = embed
        self.extra = extra
        
    async def format_page(self, entries):
        e = self.embed(title=self.extra.get('title'), description=self.extra.get('description'))
        e.set_footer(text='Use "chaihelp command" for more info on a command.')
        for command in entries:
            e.add_field(name=f'{command.name} {command.signature}', value=command.brief or "No brief given..", inline=False)
        return e
    
    
class ChaiHelpCommand(commands.HelpCommand):
    __slots__ = ()
    
    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(str(error.original))
    
    # chai help
    async def send_bot_help(self, mapping):
        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True)
        
        all_commands = {}
        for command in entries:
            if command.cog is None:
                continue
            try:
                if command.help:
                    command.help = command.help.replace('\n   ', '\n    ')
                    
                all_commands[command.cog].append(command)
            except KeyError:
                all_commands[command.cog] = [command]
        
        formatted = [value for name, value in (dict(sorted(all_commands.items(), key=lambda x: x[0].qualified_name)).items())]
        menu = DefaultHelp(formatted, embed=bot.Embed, author=self.context.author)
        await menu.start(self.context)
        
    # chai help <command>
    async def send_command_help(self, command):
        title = get_command_signature(command)
        command_help = command.help.replace('\n   ', '\n    ') if command.help else 'No help needed.'
        description = f'{command.description}\n\n{command_help}'

        embed = self.context.bot.Embed(title=title, description=description)
        await self.context.send(embed=embed)
        
    # chai help <cog>
    async def send_cog_help(self, cog):
        menu = CogHelp(cog.get_commands(), embed=self.context.bot.Embed, author=self.context.author)
        await menu.start(self.context)
        
    # chai help <group>
    async def send_group_help(self, group):
        subcommands = list(group.commands)
        if len(subcommands) == 0:
            return await self.send_command_help(subcommands)
        
        description = ''
        if group.description:
            description += group.description + '\n\n'
        if group.help:
            description += group.help.replace('\n   ', '\n    ') if group.help else 'No help given.'
        if description == '':
            description = 'No description given .'
        
        extra = dict(
            title=f'{group.qualified_name} Commands',
            description=description
        )
        menu = GroupHelp(subcommands, embed=self.context.bot.Embed, extra=extra, author=self.context.author)
        await menu.start(self.context)