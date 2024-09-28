"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to 
non-commercial purposes. Distribution, sublicensing, and sharing of this file 
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not 
misrepresent the original material. This license does not grant any 
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import traceback
from collections import defaultdict
from functools import partial
from typing import TYPE_CHECKING, Any, DefaultDict, Dict, Generator, List, Optional, Tuple, TypeAlias, Union

import discord
from discord import app_commands
from discord.ext import commands

from .context import Context
from .errors import *

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('ErrorHandler',)


_log = logging.getLogger(__name__)

Traceback: TypeAlias = Dict[str, Any]


def _resolve_role_mention(role: Union[int, str]) -> str:
    return f'<@&{role}>'


class PacketManager:
    """An extension to the error handler that keeps track of errors and sends them to a webhook.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    errors: Dict[:class:`str`, List[Dict[:class:`str`, :class:`Any`]]]
        A mapping of trace backs to their error information.
    """

    __slots__: Tuple[str, ...] = ('bot', 'cooldown', '_lock', '_most_recent', 'errors', '_code_blocker', '_error_webhook')

    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot

        self.errors: DefaultDict[str, List[Traceback]] = defaultdict(list)

        self._code_blocker: str = '```py\n{}```'
        self._error_webhook: discord.Webhook = discord.Webhook.from_url(
            os.environ['EXCEPTION_WEBHOOK_URL'], session=bot.session, bot_token=bot.http.token
        )

    def _yield_code_chunks(self, iterable: str, *, chunks: int = 2000) -> Generator[str, None, None]:
        code_blocker_size: int = len(self._code_blocker) - 2

        for i in range(0, len(iterable), chunks - code_blocker_size):
            yield self._code_blocker.format(iterable[i : i + chunks - code_blocker_size])

    async def _release_error(self, traceback_str: str, packet: Traceback) -> None:
        _log.error('Releasing error to log', exc_info=packet['exception'])

        embed = discord.Embed(title=f'An error has occurred in {packet["command"]}', timestamp=packet['time'])
        embed.add_field(
            name='Metadata',
            value='\n'.join([f'**{k.title()}**: {v}' for k, v in packet.items()]),
        )

        kwargs: Dict[str, Any] = {}
        if self.bot.user:
            kwargs['username'] = self.bot.user.display_name
            kwargs['avatar_url'] = self.bot.user.display_avatar.url

            embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

        webhook = self._error_webhook
        if webhook.is_partial():
            self._error_webhook = webhook = await self._error_webhook.fetch()

        code_chunks = list(self._yield_code_chunks(traceback_str))

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
        target: Optional[Union[Context, discord.Interaction[FuryBot]]] = None,
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
            if isinstance(target, Context):
                created = target.message.created_at
                author = target.author
            else:
                author = target.user
                created = target.created_at

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

        await self._release_error(traceback_string, packet)


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
    """

    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot

        self.__packet_manager: PacketManager = PacketManager(bot)
        self.inject()

    def inject(self) -> None:
        """A helper method to inject the error handler into the bot."""
        self.bot.tree.on_error = self.handle_tree_on_error
        self.bot.on_error = self.handle_on_error
        self.bot.on_command_error = self.handle_on_command_error  # type: ignore

    def eject(self) -> None:
        """A helper method to eject the error handler from the bot."""
        self.bot.tree.on_error = super(app_commands.CommandTree, self.bot.tree).on_error  # type: ignore -> not our fault
        self.bot.on_error = super(commands.Bot, self.bot).on_error
        self.bot.on_command_error = super(commands.Bot, self.bot).on_command_error

    @property
    def packet_manager(self) -> PacketManager:
        return self.__packet_manager

    async def log_error(
        self,
        exception: BaseException,
        *,
        target: Union[Context, discord.Interaction[FuryBot], None] = None,
        event_name: Optional[Any] = None,
    ) -> None:
        """|coro|

        A coroutine used to log an error. This will alert the user of the unknown error and add it to the exception
        manager to be handled.

        Parameters
        ----------
        exception: :class:`BaseException`
            The exception to log.
        origin: Optional[Union[:class:`Context`, :class:`discord.Interaction`]]
            The origin of the error. Can be a context or an interaction.
        event_name: Optional[:class:`str`]
            The name of the event that raised the error.
        """
        if isinstance(target, Context):
            await target.send(
                'Oh no! Something went wrong! I\'ve notified the developer to get this issue fixed, my apologies!',
                ephemeral=True,
            )

        if isinstance(target, discord.Interaction):
            if not target.response.is_done():
                await target.response.defer()

            await target.followup.send(
                'Oh no! Something went wrong! I\'ve notified the developer to get this issue fixed, my apologies!',
                ephemeral=True,
            )

        await self.__packet_manager.add_error(error=exception, target=target, event_name=event_name)

    async def _attempt_handle_known_error(
        self, target: Union[Context, discord.Interaction[FuryBot]], error: Exception
    ) -> Optional[discord.Message]:
        # We need to try and defer the given context if it has not been done yet.
        if isinstance(target, Context):
            ctx = target
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.defer(ephemeral=True)

            sender = partial(ctx.send, ephemeral=True)
        else:
            interaction = target
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            sender = partial(interaction.followup.send, ephemeral=True)

        while hasattr(error, 'original'):
            error = getattr(error, 'original')

        if isinstance(error, (AutocompleteValidationException, BadArgument)):
            return await sender(
                str(error),
            )

        if isinstance(error, app_commands.CommandInvokeError):
            # Something bad happened here, oh no!
            return await self.log_error(error.original, target=target)

        if isinstance(error, app_commands.TransformerError):
            await sender(
                content=f'Failed to convert `{error.value}` to a {error.type.name.title()}!',
            )

            # This is a development error as well, but we don't need to pass a sender
            return await self.log_error(error, target=target)

        if isinstance(error, app_commands.CheckFailure):
            if isinstance(error, app_commands.NoPrivateMessage):
                return await sender(
                    str(error),
                )
            if isinstance(error, app_commands.MissingRole):
                role: str = _resolve_role_mention(error.missing_role)
                return await sender(
                    f'You are missing the {role} role to run this command!',
                )
            if isinstance(error, app_commands.MissingAnyRole):
                roles = (_resolve_role_mention(role) for role in error.missing_roles)
                return await sender(
                    f'You\'re missing one of the following roles to run this command: {", ".join(roles)}',
                )
            if isinstance(error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)):
                fmt = 'I\'m' if isinstance(error, app_commands.BotMissingPermissions) else 'You are'
                return await sender(
                    f'{fmt} missing the following permissions to run this command: {", ".join([p.replace("_", " ").title() for p in error.missing_permissions])}',
                )

        if isinstance(error, (app_commands.CommandOnCooldown, commands.CommandOnCooldown)):
            retry_after = discord.utils.utcnow() + datetime.timedelta(seconds=error.retry_after)
            return await sender(
                f'Ope! You\'ve hit this command\'s cooldown, try again in {discord.utils.format_dt(retry_after, "R")}',
            )

        if isinstance(error, app_commands.CommandSignatureMismatch):
            await self.bot.tree.sync()
            return await sender(
                'Oh shoot! There\'s a mismatch in my commands, I\'ve synced them, try again!',
            )

        if isinstance(error, commands.MissingRequiredArgument):
            return await sender(
                f'Oop! You forgot to provide a value for `{error.param.name}`.',
            )

        if isinstance(error, commands.MissingRequiredArgument):
            return await sender(
                f'Oop! You forgot to provide a value for `{error.param.name}`.',
            )

        if isinstance(error, commands.TooManyArguments):
            return await sender(
                'Oop! You provided too many arguments for this command.',
            )

        if isinstance(error, commands.BadArgument):
            fmt = (
                str(error)
                if not (argument := getattr(error, 'argument', None))
                else f'Value for `{argument}` is not valid - {str(error)}'
            )
            return await sender(
                f'Oop! You provided an invalid value. {fmt}',
            )

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            return await sender(
                f'Ope! {error}',
            )

        if isinstance(error, commands.DisabledCommand):
            return await sender(
                'Oop! This command is disabled.',
            )

        if isinstance(error, commands.MaxConcurrencyReached):
            return await sender(
                'Oop! This command is currently running too many instances. Try again in a few minutes.',
            )

        await self.log_error(error, target=target)

    async def handle_tree_on_error(self, interaction: discord.Interaction[FuryBot], error: Exception) -> None:
        await self._attempt_handle_known_error(interaction, error=error)

    async def handle_on_command_error(self, ctx: Context, error: Exception):
        await self._attempt_handle_known_error(target=ctx, error=error)

    async def handle_on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
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
            raise RuntimeError('No error was passed to the error handler.')

        await self.__packet_manager.add_error(error=error, target=None, event_name=event_method)


async def setup(bot: FuryBot) -> None:
    bot.error_handler = ErrorHandler(bot)


async def teardown(bot: FuryBot) -> None:
    if bot.error_handler:
        bot.error_handler.eject()
