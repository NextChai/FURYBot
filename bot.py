import os
import logging
import datetime
import traceback
import aiohttp
from collections import Counter

import discord
from discord.ext import commands

import git

from cogs.utils import help_command
from cogs.utils.constants import (
    LOGGING_CHANNEL, 
    COACH_ROLE, 
    MOD_ROLE,
    BYPASS_FURY
)

from typing import Union


initial_extensions = (
    "cogs.commands",
    "cogs.events",
    "cogs.owner",
    'cogs.tasks',
    "jishaku",
)

def Embed(**kwargs):
    """
    Used to set a default bot color for our embeds.
    """
    color = discord.Color.blue()
    if kwargs.get('color'):
        color = kwargs.pop('color')
    elif kwargs.get('colour'):
        color = kwargs.pop('colour')
    
    return discord.Embed(color=color, **kwargs)

class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix=["!"], intents=discord.Intents.all(),
                         description=f"The helper bot to assist FLVS Staff.")

        self.help_command = help_command.ChaiHelp()
        self.DEFAULT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

        # Spam control
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 10, commands.BucketType.member)
        self._auto_spam_count = Counter()
        self.command_errors = {}
        
        self.Embed = Embed
        self.session = aiohttp.ClientSession()
        
        # Status stuff so I can easily change it
        self.ACTIVITY_MESSAGE = 'over the server.'
        self.ACTIVITY_TYPE = discord.ActivityType.watching
        
        
        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception as E:
                traceback.print_exc()
                print()
                
    async def on_ready(self) -> None:
        print(f"{self.user} ready: {self.user.id}")

    async def on_message(
        self, 
        message: discord.Message
    ) -> None:
        await self.process_commands(message)

    async def get_recent_commits(self):
        return [commit for commit in git.Repo(self.DEFAULT_BASE_PATH).iter_commits(max_count=10)]

    async def send_to_log_channel(
        self, 
        *args, 
        **kwargs
    ) -> discord.Message:
        channel = self.get_channel(LOGGING_CHANNEL) or (await self.fetch_channel(LOGGING_CHANNEL))
        return await channel.send(*args, **kwargs)

    async def log_spammer(
        self,
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

        embed = discord.Embed(color=discord.Color.red(), title='Auto Blocked Member')
        embed.add_field(name='Member', value=f'{message.author} (ID: {message.author.id})', inline=False)
        embed.add_field(name='Guild Info', value=f'{guild_name} (ID: {guild_id})', inline=False)
        embed.add_field(name='Channel Info', value=f'{message.channel} (ID: {message.channel.id}', inline=False)
        embed.add_field(name="What to do now?",
                        value="You've been banned from using the server. Please contact Trevor F. through DM's in order to get your access back.")

        role = discord.utils.get(ctx.guild.roles, id=802304875266179073)
        await member.add_roles(role, reason="Auto blocked member from spamming.", atomic=True)
        try:
            await member.send(embed=embed)
            could_dm = True
        except (discord.Forbidden, discord.HTTPException):
            could_dm = False
        return await ctx.send(f"<@​&{COACH_ROLE}>, <@​&{MOD_ROLE}>, {member.mention} got locked for spamming commands. I could {'not dm them' if not could_dm else 'dm them.'}")

    async def process_commands(
        self, 
        message: discord.Message
    ) -> None:
        """Edited [RoboDanny](https://github.com/Rapptz/RoboDanny) blacklist feature.
        
        https://github.com/Rapptz/RoboDanny/blob/0dfa21599da76e84c2f8e7fde0c132ec93c840a8/bot.py#L315-L347"""
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
                await self.log_spammer(ctx, message, retry_after, autoblock=True)
            else:
                await self.log_spammer(ctx, message, retry_after)
            return
        else:
            self._auto_spam_count.pop(author_id, None)

        await self.invoke(ctx)

    async def on_command_error(
        self, 
        ctx: commands.Context, 
        error: Union[commands.CommandError, Exception]  # It can be both idk
    ) -> Union[discord.Message, None]:
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

        if self.command_errors == {}:
            for command in self.commands:
                self.command_errors[command.name] = {"count": 0, "jump": [], 'traceback': [], "name": command.name}

        self.command_errors[ctx.command.name]['count'] += 1
        self.command_errors[ctx.command.name]['jump'].append(ctx.message.jump_url)

        exc = getattr(error, 'original', error)
        error_traceback = ''.join(traceback.format_exception(exc.__class__, exc, exc.__traceback__))
        self.command_errors[ctx.command.name]['traceback'].append(error_traceback)

        lines = f'Ignoring exception in command {ctx.command}:\n```py\n{error_traceback}```'
        await self.send_to_log_channel(embed=discord.Embed(description=lines))

        e.description = f"I ran into a new error..\n\n```python\n{str(error)}```"
        return await ctx.send(embed=e)
