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

from typing import Mapping, Type, Union
import discord

RULES_CHANNEL_ID: int = 763418952243347467

TEXT_CHANNEL_EMOJI: str = '<:text:1033064232767467560> '
VOICE_CHANNEL_EMOJI: str = '<:voice:1033064208457285784>'
THREAD_CHANNEL_EMOJI: str = '<:thread:1033064225133822073>'
CATEGORY_CHANNEL_EMOJI: str = '<:category:1033064217336615004> '

CHANNEL_EMOJI_MAPPING: Mapping[Type[Union[discord.abc.GuildChannel, discord.Thread]], str] = {
    discord.TextChannel: TEXT_CHANNEL_EMOJI,
    discord.VoiceChannel: VOICE_CHANNEL_EMOJI,
    discord.CategoryChannel: CATEGORY_CHANNEL_EMOJI,
    discord.Thread: THREAD_CHANNEL_EMOJI,
}
