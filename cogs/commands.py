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

"""
Mozilla Public License Version 2
================================

Copyright (c) 2016-present Rapptz

Full copyright can be found here: https://github.com/Rapptz/RoboDanny/blob/rewrite/LICENSE.txt

Please note this only applies to the "Commands.translate" function.
"""

import re
import itertools
import googletrans # type: ignore
from math import ceil
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    List,
    NamedTuple
)

import discord
from discord.ext import commands
from discord import app_commands

from jishaku.codeblocks import Codeblock, codeblock_converter # type: ignore

from utils import human_timedelta, BaseCog
from utils.context import Context
from utils.paginator import Paginator, PaginatorView

if TYPE_CHECKING:
    from bot import FuryBot
    pyston: Any
    
else:
    import pyston 

__all__ = (
    'ReportView',
    'Commands',
)

CODEBLOCK_REGEX: re.Pattern[str] = re.compile(r'`{3}(?P<lang>[a-zA-z]*)\n?(?P<code>[^`]*)\n?`{3}', flags=re.IGNORECASE)

PYTHON_OPTIMIZATION: str = """
import asyncio

async def _wrapped_execution_function():
    {}

try:
    asyncio.run(_wrapped_execution_function())
except Exception as e:
    import traceback
    traceback.print_exc()
"""


class Codeblock(NamedTuple):
    lang: str
    code: str


def codeblock_converter(argument: str) -> Codeblock:
    match = CODEBLOCK_REGEX.match(argument)
    if not match:
        raise commands.BadArgument('Invalid codeblock')

    lang, code = match.groups()
    if not lang or not code:
        raise commands.BadArgument('Invalid codeblock')

    return Codeblock(lang, code)


class JumpButton(discord.ui.Button['ReportView']):
    """Used to handle the interaciton given when the "Jump!" button is pressed
    in the ReportView.

    Attributes
    ----------
    channel_id: :class:`int`
        The channel id of the report command.
    """

    __all__ = ('channel_id',)

    def __init__(self, channel_id: int) -> None:
        self.channel_id = channel_id
        super().__init__(style=discord.ButtonStyle.green, label='Jump!')

    async def callback(self, interaction: discord.Interaction):
        """Called when the button has been interacted with.

        .. note::

            The button has to be pressed within 1 hour of the message being sent.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that gets tagged along with this button.

        Returns
        ------
        None
        """
        return await interaction.response.send_message(f'<#{self.channel_id}>', ephemeral=True)


class ReportView(discord.ui.View):
    """Passed onto :meth:`Context.send` in the `report` command.

    .. note::

        This is not locked, meaning any person who has access to the channel in which this button is called
        can press it.
    """

    __slots__ = ()

    def __init__(self, channel_id: int) -> None:
        super().__init__(timeout=3600)
        self.add_item(JumpButton(channel_id))


class Commands(BaseCog, brief='Commands!', emoji='\N{GAME DIE}'):
    """The base Commands cog for the bot.

    Any user in the server are allowed to use these commands.
    """
    pyston_client: Any = pyston.PystonClient()  # type: ignore
    pyston_allowed_languages: List[str] = []
    
    @commands.command(
        name='eval',
        brief='Evalate code',
        description='Evalate code in python.',
        aliases=['evaluate', 'ev'],
    )
    async def evaluate(
        self, ctx: Context, *, codeblock: Codeblock = commands.parameter(converter=codeblock_converter) # type: ignore
    ) -> discord.Message:
        # Let's handle internal cache first
        if not self.pyston_allowed_languages:
            runtimes = await self.pyston_client.runtimes()
            self.pyston_allowed_languages = list(itertools.chain(*([r.language, *r.aliases] for r in runtimes)))

        if codeblock.lang.lower() not in self.pyston_allowed_languages:
            return await ctx.send(f'Language `{codeblock.lang}` is not supported.')

        if codeblock.lang in {'py', 'python'}:
            codeblock = Codeblock(codeblock.lang, PYTHON_OPTIMIZATION.format(codeblock.code))

        async with ctx.typing():
            result = await self.pyston_client.execute(codeblock.lang, [pyston.File(codeblock.code)])  # type: ignore

        paginator = Paginator(prefix=f'Code lang `{codeblock.lang}` returned:\n```{codeblock.lang}')
        paginator.add_line(result.run_stage.output)

        view = None
        if len(paginator.pages) > 1:
            view = PaginatorView(paginator, author=ctx.author)

        return await ctx.send(paginator.pages[0], view=view)

    @commands.command(name='ping', description='Pong!')
    async def _ping(self, ctx: Context) -> discord.Message:
        """|coro|

        Ping the bot and return it's latency.
        """
        return await ctx.send(f'Pong! {ceil(round(self.bot.latency * 1000))}')

    @app_commands.command(name='ping', description='Pong!')
    async def ping(self, interaction: discord.Interaction) -> None:
        """|coro|

        An application command to ping the bot.
        """
        return await interaction.response.send_message(f"Pong! {ceil(round(self.bot.latency * 1000))} ms.")

    @app_commands.command(name='wave', description='Wave!')
    async def wave(self, interaction: discord.Interaction) -> None:
        """|coro|

        An application command to wave to the bot and get a ping back.
        """
        return await interaction.response.send_message(f"\N{WAVING HAND SIGN} {ceil(round(self.bot.latency * 1000))} ms.")

    @commands.command(name='report', description='Report a bug with Fury Bot.')
    @commands.guild_only()
    async def report(self, ctx: Context, message: str):
        """|coro|
        Used to report a bug with Fury Bot."""

        embed = self.bot.Embed(
            title=f'Report from {ctx.author}',
            description=f'{ctx.author.mention} used the report command in {ctx.channel.mention}',  # type: ignore
        )
        embed.add_field(name='Message', value=message)

        await self.bot.send_to_logging_channel('<@!146348630926819328>', embed=embed, view=ReportView(ctx.channel.id))

        return await ctx.reply(
            "I've reported this issue, you should get a response back from <@146348630926819328> soon, thank you!",
            ephemeral=True,
        )

    @app_commands.command(name='uptime', description='Get the current total uptime')
    async def app_command_uptime(self, interaction: discord.Interaction) -> None:
        """|coro|

        Get the current total uptime of the bot.
        """
        return await interaction.response.send_message(f'The bot has been online for {human_timedelta(self.bot.start_time)}')

    @commands.command(name='uptime', description='Get the current total uptime')
    async def uptime(self, ctx: Context) -> discord.Message:
        """|coro|

        Get the current total uptime of the bot.
        """
        return await ctx.reply(f'The bot has been online for {human_timedelta(self.bot.start_time)}', mention_author=False)

    @commands.command(name='translate', description='Translate a message from another language into english or vice versa.')
    async def translate(self, ctx: Context, *, contents: Optional[str] = None) -> Optional[discord.Message]:
        reference = ctx.message.reference
        replier = ctx.message
        if contents is None and reference is None:
            raise commands.MissingRequiredArgument(self.translate.clean_params['contents'])

        if contents is None and reference:
            resolved = reference.resolved
            if resolved and isinstance(resolved, discord.Message):
                contents = resolved.content
                replier = resolved

            if not contents and reference.cached_message:
                contents = reference.cached_message.content
                replier = reference.cached_message

            if not contents and reference.message_id:
                message = await ctx.channel.fetch_message(reference.message_id)
                replier = message
                contents = message.content

        if contents is None:
            return await ctx.send('You did not supply a message to translate.')

        translated = await self.bot.translate(contents) # type: ignore

        # Inspired by:
        # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/funhouse.py#L90-L93
        src = googletrans.LANGUAGES.get(translated.src, '(auto-detected)').title() # type: ignore
        dest = googletrans.LANGUAGES.get(translated.dest, 'Unknown').title() # type: ignore

        embed = self.bot.Embed(author=ctx.author, title='Translated Message')
        embed.add_field(name=f'From {src}', value=translated.origin, inline=False) # type: ignore
        embed.add_field(name=f'To {dest}', value=translated.text, inline=False) # type: ignore
        await replier.reply(embed=embed, mention_author=False)


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Commands(bot))
