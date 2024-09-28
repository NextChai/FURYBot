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

from typing import TYPE_CHECKING

import discord
import psutil
from discord.ext import commands

from utils import BaseCog, Context

if TYPE_CHECKING:
    from bot import FuryBot


class _AboutView(discord.ui.View):
    """Denotes the view attached to the "about" command when sent to the
    user. Contains links to the source code of the bot and the bot's support
    server invite.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(url='https://github.com/trevorflahardy/Fury-Bot', label='Source Code'))

        self.add_item(discord.ui.Button(url='https://discord.gg/mbUwbG4wAV', label='Support Server'))


class Meta(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        self.bot: FuryBot = bot
        self.process = psutil.Process()

    @commands.hybrid_command(name='about', description='Get some information about the bot.')
    async def about(self, ctx: Context) -> None:
        async with ctx.typing():
            total_members = 0
            text = 0
            voice = 0
            stage = 0
            forum = 0
            category = 0

            for guild in self.bot.guilds:
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
                    else:
                        category += 1

            total_members = f'{total_members:,}'

            embed = self.bot.Embed(
                title='Fury',
                description=(
                    f'A bot focused on moderation and utility safe for a school environment which serves '
                    f'**{total_members} members** across **{len(self.bot.guilds)}** servers.'
                ),
            )
            embed.add_field(
                name="Stats",
                value=f"Latency: `{round(self.bot.latency * 1000)} ms`\n"
                f"Client Started: {discord.utils.format_dt(self.bot.load_time, style='R')}",
            )

            memory_usage = self.process.memory_full_info().uss / 1024**2
            cpu_usage = self.process.cpu_percent() / psutil.cpu_count()
            embed.add_field(name='Current Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')

            embed.add_field(
                name='Channels',
                value=f'**{text + voice + stage + category + forum}** total\n{text} text, {voice} voice, {stage} stage, {forum} forum, {category} category.',
                inline=False,
            )

            embed.set_thumbnail(url=str(self.bot.user.display_avatar))
            await ctx.send(embed=embed, view=_AboutView())


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Meta(bot))
