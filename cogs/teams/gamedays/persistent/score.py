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
from typing_extensions import Self

import discord

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..gameday import Gameday
    from bot import FuryBot


class ScoreReportView(discord.ui.View):
    def create_embed(self, gameday: Gameday) -> None:
        ...

    @discord.ui.button(label='Report Score', style=discord.ButtonStyle.green, custom_id='score-report-view:report-score')
    async def report_score(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='Mark Gameday as Complete', custom_id='score-report-view:mark-complete')
    async def mark_complete(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...