import enum
import os
import sys
import aiohttp
import traceback as trace_lib
from collections import Counter

import urlextract
import better_profanity

from typing import (
    Optional,
    Union,
)

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping

from cogs.utils.profanity import Profanity
from cogs.reactions import ReactionView
from cogs.utils.context import Context
from cogs.utils.types import LockedOut
from cogs.utils.constants import (
    LOGGING_CHANNEL,
)

initial_extensions = (
    "cogs.commands",
    "cogs.owner",
    'cogs.tasks',
    'cogs.events.link_checker',
    'cogs.events.nsfw_pfp_checker',
    'cogs.events.on_member_join',
    'cogs.events.profanity_filter',
    'cogs.events.status_checker',
)


def Embed(**kwargs) -> discord.Embed:
    color = discord.Color.blue()
    if kwargs.get('color'):
        color = kwargs.pop('color')
    elif kwargs.get('colour'):
        color = kwargs.pop('colour')

    return discord.Embed(color=color, **kwargs)

class FuryBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            intents=discord.Intents.all(),
            description=f"The helper bot to assist FLVS Staff.",
            guild_ids=[757664675864248360]
        )

        self.DEFAULT_BASE_PATH: str = os.path.dirname(os.path.abspath(__file__))

        # Spam control
        self.spam_control: CooldownMapping = CooldownMapping.from_cooldown(10, 10, commands.BucketType.member)
        self._auto_spam_count: Counter = Counter()

        self.Embed: discord.Embed = Embed
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

        # Status stuff so I can easily change it
        self.ACTIVITY_MESSAGE = 'over the server.'
        self.ACTIVITY_TYPE = discord.ActivityType.watching

        self.locked_out: LockedOut = {} # type: ignore

        self.trnAPIHeaders = None
        self.nsfwAPI = None
        self.profanity = None
        self.extractor = None

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception:
                trace_lib.print_exc()
                print()
                
        self._load_filters()
                
    def _load_filters(self):
        self.profanity = better_profanity.profanity
        
        whitelist = ['omg', 'lmfao', 'lmao']
        with open(f"{self.DEFAULT_BASE_PATH}/txt/profanity.txt", 'r') as f:
            profanity = [word.replace('\n', '') for word in f.readlines()]
            self.profanity.add_censor_words(profanity)
        
        for index, string in enumerate(self.profanity.CENSOR_WORDSET):
            if string._original.isdigit():
                self.profanity.CENSOR_WORDSET.pop(index)
            
            if string._original not in profanity:
                self.profanity.CENSOR_WORDSET.pop(index)
        
        for index, string in enumerate(self.profanity.CENSOR_WORDSET):
            if string._original in whitelist:
                self.profanity.CENSOR_WORDSET.pop(index)
            
        self.extractor = urlextract.URLExtract()
        self.extractor.update()

    async def on_ready(self) -> None:
        print(f"{self.user} ready: {self.user.id}")
        if not self.persistent_views:
            self.add_view(ReactionView(), message_id=880941707791839252)
            
    async def on_error(self, event, *args, **kwargs):
        type, value, traceback_str = sys.exc_info()
        if not type:
            raise

        traceback = ''.join(trace_lib.format_exception(type, value, traceback_str))
        print(traceback)
        await self.send_to_log_channel(f'```python\n{traceback}\n```')
        
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if guild.id not in {757664675864248360, 851939009144029224}:
            await guild.leave()

    async def send_to_log_channel(self, *args, **kwargs) -> discord.Message:
        channel = self.get_channel(LOGGING_CHANNEL) or (await self.fetch_channel(LOGGING_CHANNEL))
        return await channel.send(*args, **kwargs)
    
    async def get_context(self, interaction: discord.Interaction, *, cls=Context):
        return await super().get_context(interaction, cls=cls)

    async def on_command_error(self, ctx: commands.Context, error: Union[commands.CommandError, Exception]) -> Optional[
        discord.Message]:
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

        e = self.Embed()

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
            e.description = "I couldn't find that role"
            return await ctx.send(embed=e)
        elif isinstance(error, commands.DisabledCommand):
            e.description = "This command has been disabled for maintenance! Don't worry though, " \
                            "we're working round clock to get it back up!"
            return await ctx.send(embed=e)
        elif isinstance(error, commands.TooManyArguments):
            e.description = f"You have too many arguments in this command! Try **{ctx.prefix}help {ctx.command.name}** for some more info on how to use this command."
            return await ctx.send(embed=e)

        exc = getattr(error, 'original', error)
        error_traceback = ''.join(trace_lib.format_exception(exc.__class__, exc, exc.__traceback__))

        lines = f'Ignoring exception in command {ctx.command}:\n```py\n{error_traceback}```'
        await self.send_to_log_channel(embed=discord.Embed(description=lines))

        e.description = f"I ran into a new error..\n\n```python\n{str(error)}```"
        return await ctx.send(embed=e)
