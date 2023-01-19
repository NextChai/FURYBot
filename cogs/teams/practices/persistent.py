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

from typing import TYPE_CHECKING, Optional
from typing_extensions import Self

import discord

if TYPE_CHECKING:
    from bot import FuryBot

    from .practice import Practice


class PracticeView(discord.ui.View):
    def __init__(self, practice: Practice):
        self.practice: Practice = practice

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        # Let's check to see if this member is already in the attending list.
        if interaction.user.id in self.practice.attending_members:
            return await interaction.response.send_message("You are already attending this practice.", ephemeral=True)

        # Let's check if this member is even on the team
        if not self.practice.team.get_member(interaction.user.id):
            return await interaction.response.send_message("You are not on this team.", ephemeral=True)

        return True

    @discord.ui.button(label='Attending')
    async def attending(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        # We're going to create a mock attending member so we can respond within 3 seconds before the database query.
        await interaction.response.defer()

        assert isinstance(interaction.user, discord.Member)
        await self.practice.handle_attending_member_join(interaction.user, interaction.created_at)

        assert interaction.message  # It's known that this won't ne none in a callback like this
        await interaction.message.edit(embed=self.practice.embed)
