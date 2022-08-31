from __future__ import annotations

import datetime
import textwrap
from typing import Any, Dict, List, Optional

import discord
from discord.ext import commands

from cogs.infractions import InfractionType
from utils import assertion
from utils.bases.cog import BaseCog


def valid_message(message: discord.Message) -> bool:
    if not message.guild:
        return False
    if not isinstance(message.author, discord.Member):
        return False
    if not message.content:
        return False

    return True


class EventListener(BaseCog):
    def check_valid_operation(self, data: Dict[Any, Any], message: discord.Message) -> bool:
        assert isinstance(message.author, discord.Member)

        if message.author.id in data['moderators']:
            return False

        author_roles = [r.id for r in message.author.roles]
        if any(role_id in author_roles for role_id in data['moderator_role_ids']):
            return False

        if message.channel.id in data['ignored_channel_ids']:
            return False

        return True

    async def validate_infraction(self, message: discord.Message, type: InfractionType) -> Optional[Dict[str, Any]]:
        assert message.guild

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                """
                SELECT 
                *
                FROM 
                (SELECT * FROM infractions.settings WHERE guild_id = $1) AS t1
                INNER JOIN
                (SELECT * FROM infractions.time WHERE guild_id = $1 AND type = $2) AS t2
                ON t1.guild_id = t2.guild_id
                """,
                message.guild.id,
                type.value,
            )

        if not data:
            return

        validation = self.check_valid_operation(dict(data), message)
        if not validation:
            return

        return dict(data)

    @commands.Cog.listener('on_links_found')
    async def on_links_found(self, message: discord.Message, links: List[str]) -> None:
        data = await self.validate_infraction(message, InfractionType.profanity)
        if not data:
            return

        assert isinstance(message.author, discord.Member)
        assert message.guild

        embed = self.bot.Embed(
            title='Links found.', description=f'You can\'t post links here, {message.author.mention}.', author=message.author
        )
        await message.channel.send(embed=embed)

        mute_delta = datetime.timedelta(seconds=data['time'])
        try:
            await message.author.timeout(mute_delta)
        except discord.Forbidden:
            pass

        channel = assertion(message.guild.get_channel(data['notification_channel_id']), Optional[discord.TextChannel])
        if not channel:
            return

        embed = self.bot.Embed(
            title='Links Found',
            description=f'I\'ve found links in {message.channel.mention} sent by {message.author.mention}',  # pyright: ignore # NOTE: Come back
            author=message.author,
        )
        embed.add_field(name='Link(s) found.', value=', '.join(f'`{link}`' for link in links))
        embed.add_field(name='Original Content', value=textwrap.shorten(message.content, 1200, placeholder='...'))
        await channel.send(embed=embed)

    @commands.Cog.listener('on_profanity_found')
    async def on_profanity_found(self, message: discord.Message, censored: str) -> None:
        data = await self.validate_infraction(message, InfractionType.links)
        if not data:
            return

        assert isinstance(message.author, discord.Member)
        assert message.guild

        embed = self.bot.Embed(
            title='Profanity Found.',
            description=f'You can\'t post that here, {message.author.mention}.',
            author=message.author,
        )
        await message.channel.send(embed=embed)

        mute_delta = datetime.timedelta(seconds=data['time'])
        try:
            await message.author.timeout(mute_delta)
        except discord.Forbidden:
            pass

        channel = assertion(message.guild.get_channel(data['notification_channel_id']), Optional[discord.TextChannel])
        if not channel:
            return

        embed = self.bot.Embed(
            title='Profanity Found',
            description=f'{message.author.mention} has sent profanity in {message.channel.mention}.',  # pyright: ignore # NOTE: Come back
            author=message.author,
        )
        embed.add_field(name='Censored', value=censored)
        embed.add_field(name='Original Content', value=message.content)
        embed.add_field(
            name='Action Taken',
            value=f'I\'ve muted them until {discord.utils.format_dt(discord.utils.utcnow() + mute_delta, "R")}',
            inline=False,
        )
        await channel.send(embed=embed)
