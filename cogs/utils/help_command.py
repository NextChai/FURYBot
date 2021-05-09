import discord
from discord.ext import menus, commands
import enum
from typing import Optional, Union


class Types(enum.Enum):
    HELP = 0
    COMMAND = 1
    GROUP = 2
    COG = 3
    MISC = 4


class BaseMenu(menus.Menu):
    def __init__(self, data: Union[dict, list], menu_type: Types, inline=True):
        super().__init__(timeout=60, clear_reactions_after=True)
        self.data = data
        self.menu_type = menu_type

        self.current_page = 0
        self.pages = {}
        self.inline = inline

        self._emojis_ = ("\U000025c0", '\U000025b6', '\U000023f9')
        if menu_type != Types.COMMAND:
            self.add_button(menus.Button(emoji="\U000025c0", action=self.on_arrow_backward))
            self.add_button(menus.Button(emoji='\U000025b6', action=self.on_arrow_forward))
            self.add_button(menus.Button(emoji='\U000023f9', action=self.on_stop_button))

    def get_embed(self, ctx: Optional[commands.Context]):
        """Gets an embed object. This does not include the fields, that gets
        added seperatley.
        
        This needs to be overwritten."""
        return discord.Embed(color=discord.Color.blue())

    def build_page_cache(self):
        """Builds the page cache from the self.data var.

        This needs to be overwritten."""
        return None

    def build_embed(self, ctx):
        """Build an embed. Is written for the default help, you may want to remove this."""
        embed = self.get_embed(ctx)
        fields = self.pages[self.current_page]
        for field in fields:
            embed.add_field(name=field.get("name"), value=field.get("value"), inline=self.inline)
        return embed

    async def send_initial_message(self, ctx, channel):
        if self.pages == {}:
            self.build_page_cache()

        embed = self.build_embed(ctx)
        return await channel.send(embed=embed)

    async def on_arrow_backward(self, payload):
        if self.current_page == 0:  # go to top page
            self.current_page = len(self.pages) - 1
        else:
            self.current_page -= 1

        embed = self.build_embed(self.ctx)
        await self.message.edit(embed=embed)

    async def on_arrow_forward(self, payload):
        if self.current_page == len(self.pages) - 1:
            self.current_page = 0
        else:
            self.current_page += 1

        embed = self.build_embed(self.ctx)
        await self.message.edit(embed=embed)

    async def on_stop_button(self, payload):
        await self.message.delete()
        self.stop()


class HelpMenu(BaseMenu):
    def __init__(self, data):
        super().__init__(data, menu_type=Types.HELP)
        self.data = data

    def get_embed(self, ctx):
        e = discord.Embed(color=discord.Color.blue(),
                          title="Categories",
                          description=f'Use "{ctx.prefix}command" for more info on a command.\n'
                                      f'Use "{ctx.prefix}category" for more info on a category.\n')
        e.set_footer(
            text=f"Page {self.current_page + 1}/{len(self.pages)} -> {len(self.ctx.bot.commands)} commands total.")
        return e

    def build_page_cache(self):
        # we need to sort the cog data to be alphabetical
        self.data = dict(sorted(self.data.items(), key=lambda x: x[0].qualified_name))
        
        for cog in self.data:
            commands = self.data[cog]
            name = cog.qualified_name
            value_cmds = ' '.join([f'`{command.name}`' for command in commands])
            value = f'{cog.description or "No description given."}\n{value_cmds}'

            highest_page = self.pages.get(len(self.pages) - 1)  # - 1 because len is 1 above indexing.
            if highest_page is None:
                self.pages[0] = [{"name": name, "value": value}]
            elif len(highest_page) == 6:
                self.pages[len(self.pages)] = [{"name": name, "value": value}]
            else:
                highest_page.append({"name": name, "value": value})


class CogMenu(BaseMenu):
    def __init__(self, data, inline=False):
        super().__init__(data, menu_type=Types.COG, inline=inline)
        self.data = data

    def get_embed(self, ctx):
        """Build the base embed, add fields later."""
        embed = discord.Embed(color=discord.Color.blue(),
                              title=self.data.get("name"),
                              description=self.data.get("description"))
        embed.set_footer(text=f'Use "{ctx.prefix}help command" for more info on a command.')
        embed.set_author(name=f"Page {self.current_page + 1}/{len(self.pages)} ({len(self.data.get('commands'))})")
        return embed

    def build_page_cache(self):
        """Builds the page cache in the self.pages var."""
        commands = self.data.get("commands")
        for command in commands:
            name = f'{command.name} {command.signature}'
            value = command.brief or command.description or command.help or "No help given.."

            highest_page = self.pages.get(len(self.pages) - 1)
            if highest_page is None:
                self.pages[0] = [{"name": name, "value": value}]
            elif len(highest_page) == 6:
                self.pages[len(self.pages)] = [{"name": name, "value": value}]
            else:
                highest_page.append({"name": name, "value": value})

    async def send_initial_message(self, ctx, channel):
        if self.pages == {}:
            self.build_page_cache()

        embed = self.build_embed(ctx)
        return await channel.send(embed=embed)


class ChaiHelp(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            'cooldown': commands.Cooldown(1, 3.0, commands.BucketType.member),
            'help': 'Shows some help about the bot, its commands, or its command groups.'
        })

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(str(error.original))

    def get_command_signature(self, command):
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

    # chai help
    async def send_bot_help(self, mapping):
        bot = self.context.bot
        commands = await self.filter_commands(bot.commands, sort=True)

        all_commands = {}
        for command in commands:
            if not command.cog:
                continue
            try:
                all_commands[command.cog].append(command)
            except:
                all_commands[command.cog] = [command]

        menu = HelpMenu(all_commands)
        await menu.start(self.context)

    # chai help <command>
    async def send_command_help(self, command):
        aliases = ", ".join(list(command.aliases))
        embed = discord.Embed(color=discord.Color.blue(),
                              title=f'{command.qualified_name} [{aliases}] {command.signature}' if aliases else f'{command.qualified_name} {command.signature}',  # ONE LINER YAYY
                              description=f'{command.description}\n\n{command.help}' if command.description else command.help or 'No help found...')
        await self.context.send(embed=embed)


    # chai help <cog>
    async def send_cog_help(self, cog):
        commands = cog.get_commands()
        package = {"name": cog.qualified_name,
                   'description': cog.description or "No description given.",
                   "commands": commands}
        menu = CogMenu(data=package)
        await menu.start(self.context)
                

    # chai help <group>
    async def send_group_help(self, group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(subcommands)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        package = {"name": f'{group.qualified_name} Commands',
                   "description": group.description or "No description given.",
                   "commands": entries}
        menu = CogMenu(data=package)
        await menu.start(self.context)
