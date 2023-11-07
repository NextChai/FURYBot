from __future__ import annotations

import asyncio
from collections import defaultdict
import datetime
import logging
import os
import sys
import traceback
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, Generator, List, Optional, Tuple, Union, TypeAlias

import discord
from discord import app_commands
from discord.ext import commands

from .context import Context
from .errors import *

if TYPE_CHECKING:
    import datetime

    from bot import FuryBot

__all__: Tuple[str, ...] = ('ErrorHandler',)


_log = logging.getLogger(__name__)

Traceback: TypeAlias = Dict[str, Any]


def _resolve_role_mention(role: Union[int, str]) -> str:
    return f'<@&{role}>'


class ExceptionManager:
    """A simple exception handler that sends all exceptions to a error
    Webhook and then logs them to the console.

    This class handles cooldowns with a simple lock, so you dont have to worry about
    rate limiting your webhook and getting banned :).

    .. note::

        If some code is raising MANY errors VERY fast and you're not there to fix it,
        this will take care of things for you.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    cooldown: :class:`datetime.timedelta`
        The cooldown between sending errors. This defaults to 5 seconds.
    errors: Dict[:class:`str`, List[Dict[:class:`str`, :class:`Any`]]]
        A mapping of tracbacks to their error information.
    code_blocker: :class:`str`
        The code blocker used to format Discord codeblocks.
    error_webhook: :class:`discord.Webhook`
        The error webhook used to send errors.
    """

    __slots__: Tuple[str, ...] = ('bot', 'cooldown', '_lock', '_most_recent', 'errors', 'code_blocker', 'error_webhook')

    def __init__(self, bot: FuryBot, *, cooldown: datetime.timedelta = datetime.timedelta(seconds=5)) -> None:
        self.bot: FuryBot = bot
        self.cooldown: datetime.timedelta = cooldown

        self._lock: asyncio.Lock = asyncio.Lock()
        self._most_recent: Optional[datetime.datetime] = None

        self.errors: DefaultDict[str, List[Traceback]] = defaultdict(list)
        self.code_blocker: str = '```py\n{}```'
        self.error_webhook: discord.Webhook = discord.Webhook.from_url(
            os.environ['EXCEPTION_WEBHOOK_URL'], session=bot.session, bot_token=bot.http.token
        )

    def _yield_code_chunks(self, iterable: str, *, chunksize: int = 2000) -> Generator[str, None, None]:
        cbs: int = len(self.code_blocker) - 2  # code blocker size

        for i in range(0, len(iterable), chunksize - cbs):
            yield self.code_blocker.format(iterable[i : i + chunksize - cbs])

    async def release_error(self, traceback: str, packet: Traceback) -> None:
        """|coro|

        Releases an error to the webhook and logs it to the console. It is not recommended
        to call this yourself, call :meth:`add_error` instead.

        Parameters
        ----------
        traceback: :class:`str`
            The traceback of the error.
        packet: :class:`dict`
            The additional information about the error.
        """
        _log.error('Releasing error to log', exc_info=packet['exception'])

        embed = discord.Embed(title=f'An error has occured in {packet["command"]}', timestamp=packet['time'])
        embed.add_field(
            name='Metadata',
            value='\n'.join([f'**{k.title()}**: {v}' for k, v in packet.items()]),
        )

        kwargs: Dict[str, Any] = {}
        if self.bot.user:
            kwargs['username'] = self.bot.user.display_name
            kwargs['avatar_url'] = self.bot.user.display_avatar.url

            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

        webhook = self.error_webhook
        if webhook.is_partial():
            self.error_webhook = webhook = await self.error_webhook.fetch()

        code_chunks = list(self._yield_code_chunks(traceback))

        embed.description = code_chunks.pop(0)
        await webhook.send(embed=embed, **kwargs)

        embeds: List[discord.Embed] = []
        for entry in code_chunks:
            embed = discord.Embed(description=entry)
            if self.bot.user:
                embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

            embeds.append(embed)

            if len(embeds) == 10:
                await webhook.send(embeds=embeds, **kwargs)
                embeds = []

        if embeds:
            await webhook.send(embeds=embeds, **kwargs)

    async def add_error(
        self,
        *,
        error: BaseException,
        target: Optional[Context] = None,
        event_name: Optional[str] = None,
    ) -> None:
        """|coro|

        Add an error to the error manager. This will handle all cooldowns and internal cache management
        for you. This is the recommended way to add errors.

        Parameters
        ----------
        error: :class:`BaseException`
            The error to add.
        ctx: Optional[:class:`DuckContext`]
            The invocation context of the error, if any.
        """
        _log.info('Adding error "%s" to log.', str(error))

        created: datetime.datetime = discord.utils.utcnow()
        author: Optional[Union[discord.Member, discord.User]] = None

        if target is not None:
            created = target.message.created_at
            author = target.author

        packet: Traceback = {'exception': error, 'time': created, 'command': 'no command'}

        if event_name:
            packet['event_name'] = event_name

        if target:
            addons: Dict[str, Optional[str]] = {
                'command': target.command and target.command.qualified_name,
                'author': author and f'<@{author.id}> ({author.id})',
                'guild': target.guild and f'{target.guild.name} ({target.guild.id})',
                'channel': target.channel and f'<#{target.channel.id}>',
            }
            packet.update(addons)

        traceback_string = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self.errors[traceback_string].append(packet)

        async with self._lock:
            # I want all other errors to be released after this one, which is why
            # lock is here. If you have code that calls MANY errors VERY fast,
            # this will ratelimit the webhook. We dont want that.

            if not self._most_recent:
                self._most_recent = discord.utils.utcnow()
                await self.release_error(traceback_string, packet)
            else:
                time_between = created - self._most_recent

                if time_between > self.cooldown:
                    self._most_recent = discord.utils.utcnow()
                    return await self.release_error(traceback_string, packet)
                else:  # We have to wait
                    _log.debug('Waiting %s seconds to release error', time_between.total_seconds())
                    await asyncio.sleep(time_between.total_seconds())

                    self._most_recent = discord.utils.utcnow()
                    return await self.release_error(traceback_string, packet)


class ErrorHandler:
    """The base error handler for the client. This is a class that listens
    for any exceptions that are raised in the bot and handles them.

    This class uses :class:`ErrorManager` to handle errors to a error webhook.

    Parameters
    ----------
    bot: :class:`FuryBot`
        The bot instance.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
        error_webhook_l
    exception_manager: :class:`ExceptionManager`
        The exception manager instance that's used to release errors.
    """

    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot

        self.exception_manager: ExceptionManager = ExceptionManager(bot)
        self.inject()

    def inject(self) -> None:
        """A helper method to inject the error handler into the bot."""
        self.bot.tree.on_error = self.handle_interaction_error
        self.bot.on_error = self.on_error
        self.bot.on_command_error = self.handle_context_error  # type: ignore

    def eject(self) -> None:
        """A helper method to eject the error handler from the bot."""
        self.bot.tree.on_error = super(app_commands.CommandTree, self.bot.tree).on_error  # type: ignore -> not our fault
        self.bot.on_error = super(commands.Bot, self.bot).on_error
        self.bot.on_command_error = super(commands.Bot, self.bot).on_command_error

    async def log_error(
        self,
        exception: BaseException,
        *,
        ctx: Context,
        event_name: Optional[Any] = None,
    ) -> None:
        """|coro|

        A coroutine used to log an error. This will alert the user of the unknown error and add it to the exception
        manager to be handled.

        Parameters
        ----------
        exception: :class:`BaseException`
            The exception to log.
        origin: Union[:class:`Context`, :class:`discord.Interaction`]
            The origin of the error.
        sender: Optional[Callable[..., Awaitable[Optional[:class:`discord.WebhookMessage`]]]]
            A sender callable to alert the user of the error.
        """
        await ctx.send(
            'Oh no! Something went wrong! I\'ve notified the developer to get this issue fixed, my apologies!',
            ephemeral=True,
        )

        await self.exception_manager.add_error(error=exception, target=ctx, event_name=event_name)

    async def _handle_error(self, ctx: Context, error: Exception) -> Optional[discord.Message]:
        # We need to try and defer the given context if it has not been done yet.
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer(ephemeral=True)

        error = getattr(error, 'original', error)

        if isinstance(error, (AutocompleteValidationException, BadArgument)):
            return await ctx.send(str(error), ephemeral=True)

        elif isinstance(error, app_commands.CommandInvokeError):
            # Something bad happened here, oh no!
            return await self.log_error(error.original, ctx=ctx)
        elif isinstance(error, app_commands.TransformerError):
            await ctx.send(content=f'Failed to convert `{error.value}` to a {error.type.name.title()}!', ephemeral=True)

            # This is a development error as well, but we don't need to pass a sender
            return await self.log_error(error, ctx=ctx)
        elif isinstance(error, app_commands.CheckFailure):
            if isinstance(error, app_commands.NoPrivateMessage):
                return await ctx.send(str(error), ephemeral=True)
            elif isinstance(error, app_commands.MissingRole):
                role: str = _resolve_role_mention(error.missing_role)
                return await ctx.send(f'You are missing the {role} role to run this command!', ephemeral=True)
            elif isinstance(error, app_commands.MissingAnyRole):
                roles = (_resolve_role_mention(role) for role in error.missing_roles)
                return await ctx.send(
                    f'You\'re missing one of the following roles to run this command: {", ".join(roles)}',
                    ephemeral=True,
                )
            elif isinstance(error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)):
                fmt = 'I\'m' if isinstance(error, app_commands.BotMissingPermissions) else 'You are'
                return await ctx.send(
                    f'{fmt} missing the following permissions to run this command: {", ".join([p.replace("_", " ").title() for p in error.missing_permissions])}',
                    ephemeral=True,
                )
        elif isinstance(error, (app_commands.CommandOnCooldown, commands.CommandOnCooldown)):
            retry_after = discord.utils.utcnow() + datetime.timedelta(seconds=error.retry_after)
            return await ctx.send(
                f'Ope! You\'ve hit this command\'s cooldown, try again in {discord.utils.format_dt(retry_after, "R")}',
                ephemeral=True,
            )
        elif isinstance(error, app_commands.CommandSignatureMismatch):
            await self.bot.tree.sync()
            return await ctx.send(
                'Oh shoot! There\'s a mismatch in my commands, I\'ve synced them, try again!', ephemeral=True
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f'Oop! You forgot to provide a value for `{error.param.name}`.', ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f'Oop! You forgot to provide a value for `{error.param.name}`.', ephemeral=True)
        elif isinstance(error, commands.TooManyArguments):
            return await ctx.send(f'Oop! You provided too many arguments for this command.', ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            fmt = (
                str(error)
                if not (argument := getattr(error, 'argument', None))
                else f'Value for `{argument}` is not valid - {str(error)}'
            )
            return await ctx.send(f'Oop! You provided an invalid value. {fmt}', ephemeral=True)
        elif isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.CheckFailure):
            return await ctx.send(f'Ope! {error}', ephemeral=True)
        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'Oop! This command is disabled.', ephemeral=True)
        elif isinstance(error, commands.MaxConcurrencyReached):
            return await ctx.send(
                f'Oop! This command is currently running too many instances. Try again in a few minutes.', ephemeral=True
            )

        await self.log_error(error, ctx=ctx)

    async def handle_interaction_error(self, interaction: discord.Interaction[FuryBot], error: Exception) -> None:
        """|coro|

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            An instance of the interaction that created the error.
        error: :class:`app_commands.AppCommandError`
            The error that was raised.
        """
        context = await self.bot.get_context(origin=interaction)
        await self._handle_error(context, error=error)

    async def handle_context_error(self, ctx: Context, error: Exception):
        await self._handle_error(ctx, error=error)

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        """|coro|

        A method called whenever there's an exception raised while processing an event.

        Parameters
        ----------
        event_name: :class:`str`
            The name of the event that raised the error.
        *args: Any
            The positional arguments that were passed to the event.
        **kwargs: Any
            The keyword arguments that were passed to the event.
        """
        # This should NEVER happen :roobulli:

        _, error, _ = sys.exc_info()
        if not error:
            raise

        await self.exception_manager.add_error(error=error, target=None, event_name=event_method)


async def setup(bot: FuryBot) -> None:
    bot.error_handler = ErrorHandler(bot)


async def teardown(bot: FuryBot) -> None:
    if bot.error_handler:
        bot.error_handler.eject()
