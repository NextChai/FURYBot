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

from typing import TYPE_CHECKING, Tuple, List

import discord

from ..team import Team

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('is_invoked_in_team_chat', 'invoker_in_team_channel_vc', 'invoker_on_team')


async def is_invoked_in_team_chat(interaction: discord.Interaction[FuryBot]) -> bool:
    """Checks to ensure the command was invoked in a team channel."""
    channel = interaction.channel
    if channel is None or isinstance(
        channel, discord.PartialMessageable
    ):  # Discord.py couldn't parse this channel (probably never happens)
        return False

    category = channel.category
    if category is None:  # They can't be in a team channel if they're not in a category
        return False

    team = Team.from_category(category.id, bot=interaction.client)
    if team is None:
        return False

    return team.text_channel_id == channel.id


async def invoker_on_team(interaction: discord.Interaction[FuryBot]) -> bool:
    # We can assume that the command was invoked in a team channel, so we can do
    # some assertions here.
    channel = interaction.channel
    assert channel
    assert not isinstance(channel, discord.PartialMessageable)

    category = channel.category
    assert category

    team = Team.from_category(category.id, bot=interaction.client)
    return bool(team.get_member(interaction.user.id))


async def invoker_in_team_channel_vc(interaction: discord.Interaction[FuryBot]) -> bool:
    """Checks to ensure the invoker is in a team voice channel."""
    # We can assume that the command was invoked in a team channel, so we can do
    # some assertions here.
    member = interaction.user
    assert isinstance(member, discord.Member)

    channel = interaction.channel
    assert channel
    assert not isinstance(channel, discord.PartialMessageable)

    category = channel.category
    assert category

    team = Team.from_category(category.id, bot=interaction.client)

    # Let's get all voice channels from this team.
    team_voice_channels: List[discord.VoiceChannel] = [team.voice_channel]

    for extra in team.extra_channels:
        if isinstance(extra, discord.VoiceChannel):
            team_voice_channels.append(extra)

    # Awesome let's check if the member's in any of these channels.
    voice_state = member.voice
    if voice_state is None:
        return False

    channel = voice_state.channel
    if channel is None:
        return False

    return channel in team_voice_channels
