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

from typing import TYPE_CHECKING, Any, Coroutine, List, Tuple

if TYPE_CHECKING:
    from bot import FuryBot


class MiniQueryBuilder:
    def __init__(self, table: str) -> None:
        self.table: str = table
        self._args: List[Tuple[str, Any]] = []
        self._conds: List[Tuple[str, Any]] = []

    @property
    def query(self) -> str:
        arg_amount: int = 1
        conds: List[str] = []
        for (predicate, _) in self._args:
            conds.append(f"{predicate} = ${arg_amount}")
            arg_amount += 1

        clauses: List[str] = []
        for (clause, _) in self._conds:
            clauses.append(f"{clause} = ${arg_amount}")
            arg_amount += 1

        formatted_conds = " , ".join(conds)
        formatted_clauses = " AND ".join(clauses)

        return f'UPDATE {self.table} SET {formatted_conds} WHERE {formatted_clauses}'

    @property
    def args(self) -> Tuple[Any, ...]:
        conds = [value for (_, value) in self._args]
        clauses = [value for (_, value) in self._conds]
        return (*conds, *clauses)

    def __call__(self, bot: FuryBot) -> Coroutine[Any, Any, str]:
        return self._execute_query(bot)

    def add_arg(self, predicate: str, value: Any) -> None:
        self._args.append((predicate, value))

    def add_condition(self, predicate: str, value: Any) -> None:
        self._conds.append((predicate, value))

    async def _execute_query(self, bot: FuryBot) -> str:
        async with bot.safe_connection() as connection:
            return await connection.execute(self.query, *self.args)
