"""
MIT License

Copyright (c) 2021 NextChai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from __future__ import annotations

import subprocess
import asyncio
from typing import (
    Any,
    Optional,
    TypeVar,
)

T = TypeVar('T')


# It runs a shell command asynchronously and returns an async iterator that yields the output of the
# command
class AsyncShellExecutor:
    def __init__(self, command: str) -> None:
        self.command: str = command
        self.task: Optional[asyncio.Task[None]] = None
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    async def _runner(self) -> None:
        process = await asyncio.create_subprocess_shell(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stream = process.stdout
        if not stream:
            return

        while True:
            line = await stream.readline()
            if line:
                try:
                    decoded = line.decode()
                except:
                    return

                await self.queue.put(decoded)
            else:
                return

    async def __aenter__(self):
        self.task = asyncio.create_task(self._runner())
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        if self.task and not self.task.cancelled() and not self.task.done():
            self.task.cancel()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.task:
            raise RuntimeError('Task was never created.')

        if self.task.done() or self.task.cancelled():
            if self.queue.qsize() > 0:
                return await self.queue.get()

            raise StopAsyncIteration

        done, _ = await asyncio.wait([self.queue.get(), self.task], return_when=asyncio.FIRST_COMPLETED)
        first = next(iter(done))
        if first == self.task:
            raise StopAsyncIteration

        return first.result()
