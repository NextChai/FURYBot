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
from typing import TYPE_CHECKING, Type

import discord
import psutil
from discord.ext import commands
from typing_extensions import Self

from utils import BaseCog, Context

if TYPE_CHECKING:
    from bot import FuryBot


class Meta(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.process = psutil.Process()

    @classmethod
    async def count_guild(
        cls: Type[Self], guild: discord.Guild, total_members: int, text: int, voice: int, stage: int, forum: int
    ) -> None:
        if guild.member_count:
            total_members += guild.member_count

        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                text += 1
            elif isinstance(channel, discord.VoiceChannel):
                voice += 1
            elif isinstance(channel, discord.StageChannel):
                stage += 1
            elif isinstance(channel, discord.ForumChannel):
                forum += 1

    @commands.hybrid_command(name='about', description='Get some information about the bot.')
    async def about(self, ctx: Context) -> None:
        async with ctx.typing():
            total_members = 0
            text = 0
            voice = 0
            stage = 0
            forum = 0
            await asyncio.gather(
                *(
                    self.bot.create_task(self.count_guild(guild, total_members, text, voice, stage, forum))
                    for guild in self.bot.guilds
                )
            )

            total_members = "{:,}".format(total_members)

            embed = self.bot.Embed(
                title='Chai',
                description=f'A bot focused on moderation and utility safe for a school environment which serves '
                f'**{total_members} members** across **{len(self.bot.guilds)}**.',
            )
            embed.add_field(
                name="Stats",
                value=f"Latency: `{round(self.bot.latency * 1000)} ms`\n"
                f"Client Started: {discord.utils.format_dt(self.bot.load_time, style='R')}",
            )
            embed.add_field(
                name='Channels', value=f'{text + voice + stage} total\n{text} text\n{voice} voice\n{stage} stage'
            )

            memory_usage = self.process.memory_full_info().uss / 1024**2
            cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
            embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')

            embed.set_thumbnail(url=str(self.bot.user.display_avatar))
            await ctx.send(embed=embed)


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Meta(bot))
