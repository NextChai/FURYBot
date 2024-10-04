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

import enum
from typing import TYPE_CHECKING, Annotated, List, Optional, Set

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, Context

from .settings import ALL_EVENTS, LoggingEvent as LoggingEvent, LoggingSettings

if TYPE_CHECKING:
    from bot import FuryBot


def guild_has_logging_settings():
    def check(ctx: Context) -> bool:
        guild = ctx.guild
        if not guild:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')

        return ctx.bot.get_logging_settings(guild.id) is not None

    return commands.check(check)


# An enum that denotes if you should display only enabled or only disabled events
# in the transverter.
class LoggingEventFilter(enum.Enum):
    ALL = 0
    ENABLED = 1
    DISABLED = 2


# TODO: Maybe some sort of way to consume List[str] events?
# This is easy to do with a converter but I'm not sure if there's a native way to support
# this in app commands (no greedy equivalent yet iirc)
class LoggingEventTransverter(commands.Converter[str], app_commands.Transformer):
    def __init__(self, logging_filter: LoggingEventFilter = LoggingEventFilter.ALL) -> None:
        self.logging_filter: LoggingEventFilter = logging_filter

    def _user_input_to_event(self, user_input: str) -> str:
        if user_input.startswith('on_'):
            user_input = user_input[3:]

        if user_input in ALL_EVENTS:
            return user_input

        # Sometimes the user will do like "Automod Rule Create", so let's
        # lower and replace spaces with underscores and check again
        user_input = user_input.lower().replace(' ', '_')
        if user_input in ALL_EVENTS:
            return user_input

        raise commands.BadArgument(f'Invalid event: {user_input}')

    async def convert(self, ctx: Context, argument: str) -> str:
        return self._user_input_to_event(argument)

    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> str:
        return self._user_input_to_event(value)

    async def autocomplete(self, interaction: discord.Interaction[FuryBot], value: str) -> List[app_commands.Choice[str]]:
        guild_id = interaction.guild_id
        if guild_id is None:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')

        settings = interaction.client.get_logging_settings(guild_id)
        choices: Set[str] = ALL_EVENTS.copy()

        if settings is None:
            # This guild has no settings, so nothing is disabled nor enabled. If the filter is
            # not ALL, then we can just return an empty list.
            if self.logging_filter is not LoggingEventFilter.ALL:
                choices = set()
        else:

            if self.logging_filter is LoggingEventFilter.ENABLED:
                choices = set((event.event_type for event in settings.logging_events))
            elif self.logging_filter is LoggingEventFilter.DISABLED:
                choices = ALL_EVENTS - set((event.event_type for event in settings.logging_events))

        return [app_commands.Choice(name=event.replace('_', ' ').title(), value=event) for event in choices]


class Logging(BaseCog):

    def _get_known_invariant_settings(self, ctx: Context) -> LoggingSettings:
        guild_id = ctx.guild and ctx.guild.id
        if not guild_id:
            raise ValueError('guild_id should be available in this context, invariant is broken. Please report this.')

        settings = self.bot.get_logging_settings(guild_id)
        if not settings:
            raise ValueError(
                'Logging settings should be available in this context, invariant is broken. Please report this.'
            )

        return settings

    @commands.hybrid_group(name='logging', description='Manage your logging settings.', invoke_without_command=True)
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @guild_has_logging_settings()
    async def logging(self, ctx: Context) -> None:
        # TODO: For now, this callback has no functionality. Look into potentially updating this such that it shows the
        # help for the command (?). Would need a default help command impl to be added back to the bot.
        ...

    @logging.command(name='channel', description='View and change the current logging channel.')
    async def logging_channel(self, ctx: Context, channel: Optional[discord.TextChannel] = None) -> discord.Message:
        async with ctx.typing(ephemeral=True):
            settings = self._get_known_invariant_settings(ctx)
            if channel is None:
                # The user is requesting to see the current logging channel.
                logging_channel_id = settings.logging_channel_id
                if logging_channel_id is None:
                    return await ctx.send('No logging channel is set.')

                logging_channel = settings.logging_channel
                if logging_channel is None:
                    # This channel was probably deleted
                    return await ctx.send(
                        f'The current logging channel was set to **{logging_channel_id}** but was deleted. No logs will be sent to the channel until it has been updated.'
                    )

                return await ctx.send(f'The current logging channel is set to {logging_channel.mention}')

            # The user is requesting to change the logging channel.
            await settings.edit(logging_channel_id=channel.id)
            return await ctx.send(f'I have updated the logging channel to {channel.mention}.')

    @logging.group(name='events', description='Manage the enabled and disabled logging events.')
    @guild_has_logging_settings()
    async def logging_events(self, ctx: Context) -> discord.Message:
        return await ctx.send('Please specify a subcommand.')

    @logging_events.command(name='enable', description='Enable a logging event.')
    async def logging_events_enable(
        self, ctx: Context, event: Annotated[str, LoggingEventTransverter(LoggingEventFilter.DISABLED)]
    ) -> discord.Message:
        async with ctx.typing(ephemeral=True):
            settings = self._get_known_invariant_settings(ctx)
            logging_event = await settings.create_logging_event(event_type=event)
            return await ctx.send(f'I have enabled logging events for **{logging_event.human_readable_event_type}**.')

    @logging_events.command(name='disable', description='Disable a logging event.')
    async def logging_events_disable(
        self, ctx: Context, event: Annotated[str, LoggingEventTransverter(LoggingEventFilter.ENABLED)]
    ) -> discord.Message:
        async with ctx.typing():
            settings = self._get_known_invariant_settings(ctx)
            logging_event = settings.get_logging_event(event)
            if logging_event is None:
                return await ctx.send(f'Logging events for **{event}** are already disabled.')

            await logging_event.delete()
            return await ctx.send(f'Logging events for **{event}** have been disabled.')

    @logging_events.command(name='enable-all', description='Enable all logging events.')
    async def logging_events_enable_all(self, ctx: Context) -> discord.Message:
        async with ctx.typing():
            settings = self._get_known_invariant_settings(ctx)
            await settings.create_all_possible_logging_events()
            return await ctx.send('All logging events have been enabled.')

    @logging_events.command(name='disable-all', description='Disable all logging events.')
    async def logging_events_disable_all(self, ctx: Context) -> discord.Message:
        async with ctx.typing():
            settings = self._get_known_invariant_settings(ctx)
            await settings.delete_all_logging_events()
            return await ctx.send('All logging events have been disabled.')


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Logging(bot))
