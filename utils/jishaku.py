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

import io
import contextlib
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeVar,
)

import discord

from jishaku.cog import STANDARD_FEATURES, OPTIONAL_FEATURES
from jishaku.features.python import PythonFeature
from jishaku.codeblocks import codeblock_converter
from jishaku.exception_handling import ReplResponseReactor
from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.functools import AsyncSender
from jishaku.repl import AsyncCodeExecutor, get_var_dict_from_ctx
from jishaku.paginators import use_file_check, PaginatorInterface, WrappedPaginator

from utils import BaseCog

from .context import Context

if TYPE_CHECKING:
    from bot import FuryBot

T = TypeVar('T')


class Jishaku(BaseCog, *STANDARD_FEATURES, *OPTIONAL_FEATURES, emoji='\N{CONSTRUCTION WORKER}', brief='Jishaku Frontend.'):
    """
    The jishaku frontend class that mixes all Features alongside BaseCog functionality.

    This adds utility commands to the bot that allow for the execution of code in
    discord, debugging, etc.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    """

    __is_jishaku__: bool = True

    async def jsk_python_result_handling(
        self,
        ctx: Context,
        result: Any,
        *,
        redirect_stdout: Optional[str] = None,
    ) -> Optional[discord.Message]:
        if isinstance(result, discord.Message):
            return await ctx.send(f'<Message <{result.jump_url}>>')

        elif isinstance(result, discord.File):
            return await ctx.send(file=result)

        elif isinstance(result, discord.Embed):
            return await ctx.send(embed=result)

        elif isinstance(result, PaginatorInterface):
            return await result.send_to(ctx)

        if not isinstance(result, str):
            result = repr(result)

        stripper = '**Redirected stdout**:\n{}'
        total = 2000
        if redirect_stdout:
            total -= len(f'{stripper.format(redirect_stdout)}\n')

        if len(result) <= total:
            if result.strip == '':
                result = '\u200b'

            if redirect_stdout:
                result = f'{stripper.format(redirect_stdout)}\n{result}'

            return await ctx.send(result.replace(self.bot.http.token, "[token omitted]"))  # type: ignore

        if use_file_check(ctx, len(result)):  # File "full content" preview limit
            # Discord's desktop and web client now supports an interactive file content
            #  display for files encoded in UTF-8.
            # Since this avoids escape issues and is more intuitive than pagination for
            #  long results, it will now be prioritized over PaginatorInterface if the
            #  resultant content is below the filesize threshold
            return await ctx.send(file=discord.File(filename="output.py", fp=io.BytesIO(result.encode('utf-8'))))

        # inconsistency here, results get wrapped in codeblocks when they are too large
        #  but don't if they're not. probably not that bad, but noting for later review
        paginator = WrappedPaginator(prefix='```py', suffix='```', max_size=1985)

        if redirect_stdout:
            for chunk in self.bot.chunker(f'{stripper.format(redirect_stdout).replace("**", "")}\n', size=1975):
                paginator.add_line(chunk)

        for chunk in self.bot.chunker(result, size=1975):
            paginator.add_line(chunk)

        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        return await interface.send_to(ctx)

    @discord.utils.copy_doc(PythonFeature.jsk_python)
    @Feature.Command(parent='jsk', name='py', aliases=['python'])
    async def jsk_python(self, ctx: Context, *, argument: codeblock_converter) -> None:
        """|coro|

        The subclassed jsk python command to implement some more functionality and features.

        Added
        -----
        - :meth:`contextlib.redirect_stdout` to allow for print statements.
        - :meth:`utils.add_logging` and `self` to the scope.

        Parameters
        ----------
        argument: :class:`str`
            The code block to evaluate and return.
        """

        arg_dict = get_var_dict_from_ctx(ctx, Flags.SCOPE_PREFIX)
        # arg_dict['add_logging'] = add_logging
        arg_dict['self'] = self
        arg_dict['_'] = self.last_result

        scope = self.scope
        printed = io.StringIO()

        try:
            async with ReplResponseReactor(ctx.message):
                with self.submit(ctx):
                    with contextlib.redirect_stdout(printed):
                        executor = AsyncCodeExecutor(argument.content, scope, arg_dict=arg_dict)

                        # Absolutely a garbage lib that I have to fix jesus christ.
                        # I have to rewrite this lib holy jesus its so bad.
                        async for send, result in AsyncSender(executor):
                            self.last_result = result

                            value = printed.getvalue()
                            send(
                                await self.jsk_python_result_handling(
                                    ctx,
                                    result,
                                    redirect_stdout=None if value == '' else value,
                                )
                            )
        finally:
            scope.clear_intersection(arg_dict)


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Jishaku(bot=bot))
