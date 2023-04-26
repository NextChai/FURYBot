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

import asyncio
import datetime
import inspect
import io
import re
import textwrap
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional, Tuple

import discord
from discord.ext import commands

from utils import BaseCog, Context, human_timedelta, human_timestamp, make_table

if TYPE_CHECKING:
    from bot import FuryBot

FLAG_REGEX = re.compile(
    r'\-{2}(?P<arg_name>\w+)\=(?P<arg_content>(?:\`){3}python\n(?P<arg_code_content>(?:.+\n)+)(?:\`){3}|(?:[a-z0-9\s\.])+)'
)
BRACKET_REGEX = re.compile(r'(?:(?:\{(?P<bracket_content>(?:.|\n)+?)\}))')
ARG_REGEX = re.compile(
    r'\$(?P<arg_number>\d+)=(?P<arg_content>(?:`{3}python\n(?P<arg_code_content>.*?)`{3}|\S+(?:(?:\r?\n(?!\$)\s*)+(?P<arg_text_content>.*?)\s*)?))(?=\s*\$|\Z)',
    re.MULTILINE | re.DOTALL,
)
CODEBLOCK_REGEX = re.compile(r'`{3}(?P<lang>[a-zA-z]*)\n?(?P<code>[^`]*)\n?`{3}')


class SQLFlagConverter(commands.Converter[Tuple[str, List[Any]]]):

    # A method name to convert a string to something that psql can easily understand.
    def convert_to_psql(self, item: Any) -> str:
        if isinstance(item, str):
            return f"'{item}'"
        elif isinstance(item, datetime.datetime):
            return f"'{item.isoformat()}'"
        elif isinstance(item, datetime.date):
            return f"'{item.isoformat()}'"
        elif isinstance(item, datetime.time):
            return f"'{item.isoformat()}'"
        elif isinstance(item, bool):
            return str(item).lower()

        return str(item)

    async def convert_flag(self, ctx: Context, flag_content: str, is_code_blocked: bool) -> Any:
        env: Dict[str, Any] = {
            'bot': ctx.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'MISSING': discord.utils.MISSING,
            'human_timestamp': human_timestamp,
            'human_timedelta': human_timedelta,
            'View': discord.ui.View,
            'Button': discord.ui.Button,
        }
        env.update(globals())

        return_keyword = 'return ' if not is_code_blocked else ''
        wrapped_codeblock = textwrap.dedent(
            f"""
            async def __wrapped_codeblock():
                {return_keyword}{flag_content}
            """
        )

        exec(wrapped_codeblock, env)

        wrapped_function: Callable[[], Coroutine[Any, Any, Any]] = env['__wrapped_codeblock']

        result = await wrapped_function()

        if inspect.iscoroutine(result):
            result = await result
        elif inspect.iscoroutinefunction(result):
            result = await result()
        elif inspect.isfunction(result):
            result = await asyncio.to_thread(result)

        return result

    async def convert(self, ctx: Context, argument: str) -> Tuple[str, List[Any]]:
        # Let's search for any flags passed to this argument and remove them.
        # After, we could only be left with our SQL statement.
        flags = FLAG_REGEX.findall(argument)
        converted_flags: Dict[str, str] = {}

        for (flag_name, flag_content, code_block_content) in flags:
            flag_full_name = f'--{flag_name}={flag_content}'

            # Remove the flag from the argument
            argument = argument.replace(flag_full_name, '')

            # Convert the flag content
            try:
                converted = await self.convert_flag(ctx, code_block_content or flag_content, bool(code_block_content))
            except Exception as exc:
                raise commands.BadArgument(f'Failed to convert flag "{flag_name}".') from exc

            converted_flags[flag_name] = self.convert_to_psql(converted)

        converted_args: Dict[int, Any] = {}
        args = ARG_REGEX.findall(argument)
        for (arg_number, arg_content, code_block_content, *_) in args:
            full_arg_name = f'${arg_number}={arg_content}'

            # Remove the arg from the argument
            argument = argument.replace(full_arg_name, '')

            # Convert the arg content
            try:
                converted = await self.convert_flag(ctx, code_block_content or arg_content, bool(code_block_content))
            except Exception as exc:
                raise commands.BadArgument(f'Failed to convert arg "{arg_number}".') from exc

            converted_args[int(arg_number)] = self.convert_to_psql(converted)

        # We should only be left with the SQL statement now
        query = argument.strip()

        # If this is a codeblock we need to remove the codeblock formatting.
        match = CODEBLOCK_REGEX.match(query)
        if match is not None:
            query = match.group('code')

        # Let's look for any brackets that point to a flag or an inlined bracket code block.
        brackets = BRACKET_REGEX.findall(query)
        for bracket_content in brackets:
            existing_flag = converted_flags.get(bracket_content, discord.utils.MISSING)
            if existing_flag is not discord.utils.MISSING:
                query = query.replace(f'{{{bracket_content}}}', existing_flag)
                continue

            # This is a code block, we can convert it and replace it with the result.
            try:
                converted = await self.convert_flag(ctx, bracket_content, False)
            except Exception as exc:
                raise commands.BadArgument(f'Failed to convert bracket code block "{bracket_content}".') from exc

            query = query.replace(f'{{{bracket_content}}}', self.convert_to_psql(converted))

        return query, [arg for i in range(1, len(converted_args) + 1) if (arg := converted_args.get(i, None))]


class Owner(BaseCog):
    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    async def _common_sql(self, method: str, query: str, *args: Any) -> Any:
        async with self.bot.safe_connection() as connection:
            coro = getattr(connection, method)

            return await coro(query, *args)

    async def _send_table(self, ctx: Context, table: str) -> discord.Message:
        # If the first line of the table is more than 125 chars, we need to send it in a file.
        comfy_discord_length = 100
        first_line_length = len(table.split('\n')[0])

        if first_line_length > comfy_discord_length:
            # Send it in a .txt file
            file = discord.File(
                fp=io.BytesIO(table.encode('utf-8')), filename='result.txt', description='Result of the SQL query.'
            )
            return await ctx.send(file=file)

        return await ctx.send(f'```{table}```')

    @commands.group(name='sql', description='Does a SQL query and returns the results.', invoke_without_command=True)
    async def sql(
        self,
        ctx: Context,
        *,
        query_args: Tuple[str, List[Any]] = commands.parameter(
            converter=SQLFlagConverter, description='The query you want to pass along.'
        ),
    ) -> Optional[discord.Message]:
        await ctx.invoke(self.sql_execute, query_args=query_args)

    @sql.command(name='execute', description='Execute a given SQL query and returns the results.')
    async def sql_execute(
        self,
        ctx: Context,
        *,
        query_args: Tuple[str, List[Any]] = commands.parameter(
            converter=SQLFlagConverter, description='The query you want to pass along.'
        ),
    ) -> Optional[discord.Message]:
        async with ctx.typing():
            query, args = query_args

            result = await self._common_sql('execute', query, *args)
            return await ctx.send(f'Executed query. Result: `{result}`')

    @sql.command(name='fetch', description='Fetches a given SQL query and returns the results.')
    async def sql_fetch(
        self,
        ctx: Context,
        *,
        query_args: Tuple[str, List[Any]] = commands.parameter(
            converter=SQLFlagConverter, description='The query you want to pass along.'
        ),
    ) -> discord.Message:
        async with ctx.typing():
            query, args = query_args

            result = await self._common_sql('fetch', query, *args)

            if not result:
                return await ctx.send(f'`{result}`')

            # Make a table from this result
            table = make_table(rows=[list(dict(entry).values()) for entry in result], labels=list(dict(result[0]).keys()))

            return await self._send_table(ctx, table)

    @sql.command(name='fetchrow', description='Fetches a given SQL query and returns the first row.')
    async def sql_fetchrow(
        self,
        ctx: Context,
        *,
        query_args: Tuple[str, List[Any]] = commands.parameter(
            converter=SQLFlagConverter, description='The query you want to pass along.'
        ),
    ) -> discord.Message:
        async with ctx.typing():
            query, args = query_args

            result = await self._common_sql('fetchrow', query, *args)
            if not result:
                return await ctx.send(f'`{result}`')

            table = make_table(rows=[list(dict(result).values())], labels=list(dict(result).keys()))
            return await self._send_table(ctx, table)

    @sql.command(name='fetchval', description='Fetches a given SQL query and returns the first value.')
    async def sql_fetchval(
        self,
        ctx: Context,
        *,
        query_args: Tuple[str, List[Any]] = commands.parameter(
            converter=SQLFlagConverter, description='The query you want to pass along.'
        ),
    ) -> discord.Message:
        async with ctx.typing():
            query, args = query_args

            result = await self._common_sql('fetchval', query, *args)
            return await ctx.send(f'`{result}`')


async def setup(bot: FuryBot):
    await bot.add_cog(Owner(bot))
