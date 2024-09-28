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

from typing import TYPE_CHECKING, Any, Coroutine, List, Optional, Tuple

if TYPE_CHECKING:
    from bot import ConnectionType

__all__: Tuple[str, ...] = ('QueryBuilder',)


class QueryBuilder:
    def __init__(self, table: str) -> None:
        self.table: str = table
        self._args: List[Tuple[str, Any]] = []
        self._conds: List[Tuple[str, Any]] = []

    @property
    def query(self) -> str:
        arg_amount: int = 1
        conds: List[str] = []
        for predicate, _ in self._args:
            conds.append(f"{predicate} = ${arg_amount}")
            arg_amount += 1

        clauses: List[str] = []
        for clause, _ in self._conds:
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

    def __call__(self, connection: ConnectionType) -> Coroutine[Any, Any, Optional[str]]:
        return self._execute_query(connection)

    def add_arg(self, predicate: str, value: Any) -> None:
        self._args.append((predicate, value))

    def add_condition(self, predicate: str, value: Any) -> None:
        self._conds.append((predicate, value))

    async def _execute_query(self, connection: ConnectionType) -> Optional[str]:
        if not self._args:
            return

        return await connection.execute(self.query, *self.args)
