import discord
from discord.ext import commands
import os
import logging

from cogs.utils import help_command



initial_extensions = (
    "cogs.moderation",
    "cogs.events",
    "cogs.owner",
    "jishaku",
)

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix = ["!"], intents=discord.Intents.all(),
        description = f"The helper bot to assist FLVS Staff.")
        
        self.help_command = help_command.ChaiHelp()
        self.DEFAULT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception as E:
                print(E)

    async def on_ready(self):
        print(f"{self.user} ready: {self.user.id}")
        
    async def on_handle_update(self, extensions: list, channel):
        logging.info(extensions)  # I did this here to ensure the event was getting dispatched
        
        e = discord.Embed(color=discord.Color.blue())
        for extension in extensions:
            try:
                self.reload_extension(extension)
                e.add_field(name=extension, value="Reloded")
            except Exception as exc:
                e.add_field(name=extension, value=f'```python\n{exc}```')
        return await channel.send(embed=e)
        
    async def on_message(self, message):
        await self.process_commands(message)
        
    async def send_to_log_channel(self, embed: discord.Embed):
        channel = self.get_channel(765631488506200115) or (await self.fetch_channel(765631488506200115))
        await channel.send(embed=embed)
        
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound,)
        error = getattr(error, 'original', error)
        if isinstance(error, ignored):
            return

        e = discord.Embed(color=discord.Color.blue())
        
        if isinstance(error, commands.MissingRequiredArgument):
            e.description = f"{error.param} is a required argument that's missing."
            return await ctx.send(embed=e)
        if isinstance(error, commands.CommandOnCooldown):
            e.description = str(error)
            return await ctx.send(embed=e)
        if isinstance(error, commands.ChannelNotFound):
            e.description = 'I was unable to find this channel. You can either type in the channel name, or mention it with a *#*.'
            return await ctx.send(embed=e)
        elif isinstance(error, commands.MissingAnyRole):
            e.description = "You're missing some roles to do this!"
            return await ctx.send(embed=e)
        elif isinstance(error, commands.RoleNotFound):
            e.description = "I could't find that role"
            return await ctx.send(embed=e)
        elif isinstance(error, commands.DisabledCommand):
            e.description = "This command has been disabled for maintenance! Don't worry though, " \
                            "we're working round clock to get it back up!"
            return await ctx.send(embed=e)
        elif isinstance(error, commands.TooManyArguments):
            e.description =  f"You have too many arguments in this command! Try **{ctx.prefix}help {ctx.command.name}** for some more info on how to use this command."
            return await ctx.send(embed=e)

        if not hasattr(self, "command_errors"):
            self.command_errors = {}

        try:
            self.command_errors[ctx.command.name]['count'] += 1
            self.command_errors[ctx.command.name]['jump'].append(ctx.message.jump_url)
        except KeyError:
            self.command_errors[ctx.command.name]['count'] = 1
            self.command_errors[ctx.command.name]['jump'] = [ctx.message.jump_url]

        e.description = f"I ran into a new error..\n\n```python\n{str(error)}```"
        return await ctx.send(embed=e)

        