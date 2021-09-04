import os
import sys
import logging
import datetime
import aiohttp
import traceback as trace_lib
from collections import Counter

import urlextract
import better_profanity

from typing import (
    Optional,
    Union,
    Dict,
    Any,
    List
)

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import CooldownMapping

from cogs.utils.help_command import ChaiHelpCommand
from cogs.reactions import ReactionView
from cogs.utils.context import Context
from cogs.utils.types import LockedOut
from cogs.utils.constants import (
    LOGGING_CHANNEL,
    COACH_ROLE,
    MOD_ROLE,
    BYPASS_FURY
)

initial_extensions = (
    "cogs.commands",
    'cogs.overwatch',
    "cogs.owner",
    'cogs.tasks',
    'cogs.events.link_checker',
    'cogs.events.nsfw_name_checker',
    'cogs.events.nsfw_pfp_checker',
    'cogs.events.on_member_join',
    'cogs.events.profanity_filter',
    'cogs.events.status_checker',
    "jishaku",
)


def Embed(**kwargs) -> discord.Embed:
    color = discord.Color.blue()
    if kwargs.get('color'):
        color = kwargs.pop('color')
    elif kwargs.get('colour'):
        color = kwargs.pop('colour')

    return discord.Embed(color=color, **kwargs)


async def log_spammer(
    ctx: commands.Context,
    message: discord.Message,
    retry_after: float,
    autoblock: bool = False
) -> Union[discord.Message, None]:
    """
    Edited [RoboDanny](https://github.com/Rapptz/RoboDanny) log_spammer feature.
    
    https://github.com/Rapptz/RoboDanny/blob/0dfa21599da76e84c2f8e7fde0c132ec93c840a8/bot.py#L299-L313
    """
    guild_name = getattr(ctx.guild, 'name', 'No Guild (DMs)')
    guild_id = getattr(ctx.guild, 'id', None)
    fmt = 'User %s (ID %s) in guild %r (ID %s) spamming, retry_after: %.2fs'
    logging.warning(fmt, message.author, message.author.id, guild_name, guild_id, retry_after)
    if not autoblock:
        return

    member = ctx.author
    if not isinstance(member, discord.Member):
        return None

    embed = Embed(title='Auto Blocked Member')
    embed.add_field(name='Member', value=f'{message.author} (ID: {message.author.id})', inline=False)
    embed.add_field(name='Guild Info', value=f'{guild_name} (ID: {guild_id})', inline=False)
    embed.add_field(name='Channel Info', value=f'{message.channel} (ID: {message.channel.id}', inline=False)
    embed.add_field(
        name="What to do now?",
        value="You've been banned from using the server. Please contact Trevor F. through DM's in order to get your "
              "access back.")

    role = discord.utils.get(ctx.guild.roles, id=802304875266179073)
    await member.add_roles(role, reason="Auto blocked member from spamming.", atomic=True)
    try:
        await member.send(embed=embed)
        could_dm = True
    except (discord.Forbidden, discord.HTTPException):
        could_dm = False
    return await ctx.send(
        f"<@​&{COACH_ROLE}>, <@​&{MOD_ROLE}>, {member.mention} got locked for spamming commands. I could {'not dm them' if not could_dm else 'dm them.'}")


class FuryBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=["!"],
            intents=discord.Intents.all(),
            description=f"The helper bot to assist FLVS Staff.",
            help_command=ChaiHelpCommand()
        )

        self.DEFAULT_BASE_PATH: str = os.path.dirname(os.path.abspath(__file__))

        # Spam control
        self.spam_control: CooldownMapping = CooldownMapping.from_cooldown(10, 10, commands.BucketType.member)
        self._auto_spam_count: Counter = Counter()
        self.command_errors: Dict[Any, Any] = {}

        self.Embed: discord.Embed = Embed
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

        # Status stuff so I can easily change it
        self.ACTIVITY_MESSAGE = 'over the server.'
        self.ACTIVITY_TYPE = discord.ActivityType.watching

        self.locked_out: LockedOut = {}

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
        custom_words: List[str] = ['chode', 'dick']
        
        with open(f"{self.DEFAULT_BASE_PATH}/txt/profanity.txt", 'r') as f:
            extra_profanity = f.readlines()
            extra_profanity = list(dict.fromkeys(extra_profanity))  # clear up duplicates
            extra_profanity += custom_words
            self.profanity.add_censor_words(extra_profanity)
            
        with open(f"{self.DEFAULT_BASE_PATH}/txt/whitelist.txt", 'r') as f:
            whitelist = f.readlines()
            
        self.extractor = urlextract.URLExtract()
        self.extractor.update()

        for index, string in enumerate(self.profanity.CENSOR_WORDSET):
            if self.profanity.CENSOR_WORDSET[index]._original.isdigit():
                self.profanity.CENSOR_WORDSET.pop(index)
            if string._original in whitelist:
                self.profanity.CENSOR_WORDSET.pop(index)

    async def on_ready(self) -> None:
        print(f"{self.user} ready: {self.user.id}")
        if not self.persistent_views:
            self.add_view(ReactionView(), message_id=880941707791839252)

    async def on_message(self, message: discord.Message) -> None:
        await self.process_commands(message)

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

    async def send_to_log_channel(
        self,
        *args,
        **kwargs
    ) -> discord.Message:
        channel = self.get_channel(LOGGING_CHANNEL) or (await self.fetch_channel(LOGGING_CHANNEL))
        return await channel.send(*args, **kwargs)

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)

    async def process_commands(self, message: discord.Message) -> None:
        """
        Edited [RoboDanny](https://github.com/Rapptz/RoboDanny) blacklist feature.
        
        https://github.com/Rapptz/RoboDanny/blob/0dfa21599da76e84c2f8e7fde0c132ec93c840a8/bot.py#L315-L347
        """
        ctx = await self.get_context(message)

        if ctx.guild is None:
            return await self.invoke(ctx)

        if not isinstance(ctx.author, discord.User):
            role = discord.utils.get(ctx.guild.roles, id=BYPASS_FURY)  # Bypass Fury Role
            if role in ctx.author.roles:
                return await self.invoke(ctx)

        bucket = self.spam_control.get_bucket(message)
        current = message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp()
        retry_after = bucket.update_rate_limit(current)
        author_id = message.author.id

        if retry_after and author_id != self.owner_id:
            self._auto_spam_count[author_id] += 1
            if self._auto_spam_count[author_id] >= 5:
                del self._auto_spam_count[author_id]
                await log_spammer(ctx, message, retry_after, autoblock=True)
            else:
                await log_spammer(ctx, message, retry_after)
            return
        else:
            self._auto_spam_count.pop(author_id, None)

        await self.invoke(ctx)

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

        try:
            self.command_errors[ctx.command.name]['count'] += 1
            self.command_errors[ctx.command.name]['jump'].append(ctx.message.jump_url)
        except KeyError:
            self.command_errors[ctx.command.name] = {'count': 0, 'jump': [], 'traceback': []}
            self.command_errors[ctx.command.name]['count'] += 1
            self.command_errors[ctx.command.name]['jump'].append(ctx.message.jump_url)

        exc = getattr(error, 'original', error)
        error_traceback = ''.join(trace_lib.format_exception(exc.__class__, exc, exc.__traceback__))
        self.command_errors[ctx.command.name]['traceback'].append(error_traceback)

        lines = f'Ignoring exception in command {ctx.command}:\n```py\n{error_traceback}```'
        await self.send_to_log_channel(embed=discord.Embed(description=lines))

        e.description = f"I ran into a new error..\n\n```python\n{str(error)}```"
        return await ctx.send(embed=e)
