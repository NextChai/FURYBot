import datetime
import logging
import os
import traceback
from collections import Counter

import discord
import git
from discord.ext import commands

from cogs.utils import help_command


initial_extensions = (
    "cogs.commands",
    "cogs.events",
    "cogs.owner",
    "jishaku",
)


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=["!"], intents=discord.Intents.all(),
                         description=f"The helper bot to assist FLVS Staff.")

        self.help_command = help_command.ChaiHelp()
        self.DEFAULT_BASE_PATH = os.path.dirname(os.path.abspath(__file__))

        # Spam control
        self.spam_control = commands.CooldownMapping.from_cooldown(10, 10, commands.BucketType.member)
        self._auto_spam_count = Counter()
        self.command_errors = {}

        for extension in initial_extensions:
            try:
                self.load_extension(extension)
            except Exception as E:
                print(E)

    async def on_ready(self):
        print(f"{self.user} ready: {self.user.id}")

    async def on_message(self, message):
        await self.process_commands(message)

    async def on_handle_update(self, extensions: list, channel, raw_message):
        logging.info(extensions)  # I did this here to ensure the event was getting dispatched

        e = discord.Embed(color=discord.Color.blue(), description=f"```py\n{raw_message}```")
        for extension in extensions:
            try:
                self.reload_extension(extension)
                e.add_field(name=extension, value="Reloded")
            except Exception as exc:
                e.add_field(name=extension, value=f'```python\n{exc}```')
        return await channel.send(embed=e)

    async def sync(self):
        change = git.cmd.Git(self.DEFAULT_BASE_PATH).pull('https://github.com/NextChai/FURYBot', 'main')
        return change

    async def get_recent_commits(self):
        return [commit for commit in git.Repo(self.DEFAULT_BASE_PATH).iter_commits(max_count=10)]

    async def send_to_log_channel(self, embed: discord.Embed):
        channel = self.get_channel(765631488506200115) or (await self.fetch_channel(765631488506200115))
        await channel.send(embed=embed)

    @staticmethod
    async def log_spammer(ctx: commands.Context,
                          message: discord.Message,
                          retry_after,
                          autoblock: bool = False):
        """Edited [RoboDanny](https://github.com/Rapptz/RoboDanny) log_spammer feature.
        
        https://github.com/Rapptz/RoboDanny/blob/0dfa21599da76e84c2f8e7fde0c132ec93c840a8/bot.py#L299-L313"""
        guild_name = getattr(ctx.guild, 'name', 'No Guild (DMs)')
        guild_id = getattr(ctx.guild, 'id', None)
        fmt = 'User %s (ID %s) in guild %r (ID %s) spamming, retry_after: %.2fs'
        logging.warning(fmt, message.author, message.author.id, guild_name, guild_id, retry_after)
        if not autoblock:
            return

        member = ctx.author
        if not isinstance(member, discord.Member):
            return

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
        await ctx.send(
            content=f"<@146348630926819328>, {member.mention} got locked. I could {'not dm them' if not could_dm else 'dm them.'}")

    async def process_commands(self, message):
        """Edited [RoboDanny](https://github.com/Rapptz/RoboDanny) blacklist feature.
        
        https://github.com/Rapptz/RoboDanny/blob/0dfa21599da76e84c2f8e7fde0c132ec93c840a8/bot.py#L315-L347"""
        ctx = await self.get_context(message)

        if ctx.guild is None:
            return await self.invoke(ctx)

        role = discord.utils.get(ctx.guild.roles, id=802948019376488511)  # Bypass Fury Role
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
