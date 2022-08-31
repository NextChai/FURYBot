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

import enum
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from utils.bases.cog import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot

class InfractionType(enum.Enum):
    profanity = 'Profanity'
    links = 'Links'


class Infractions(BaseCog):

    infraction = app_commands.Group(
        name='infraction',
        description='Manage infractions.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
    )

    infraction_moderator = app_commands.Group(
        name='moderator',
        description='Manage infraction moderators.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
    )
    
    infraction_moderator_role = app_commands.Group(
        name='moderator_role',
        description='Manage infraction moderator roles.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
    )
    
    infraction_allowed_links = app_commands.Group(
        name='allowed_links',
        description='Add and remove allowed links.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
    )
    
    infraction_ignored_channels = app_commands.Group(
        name='ignored_channels',
        description='Manage ignored channels for the infraction manager.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
    )

    @infraction.command(name='notification_channel', description='Change the notification channel for infractions.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    @app_commands.describe(channel='The channel to set for notifications.')
    async def infraction_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT * FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET notification_channel_id = $2
                    ELSE
                        INSERT INTO infractions.settings(guild_id, notification_channel_id) VALUES($1, $2)
                    END IF;
                """,
                interaction.guild.id,
                channel.id,
            )

        return await interaction.response.send_message(
            f'I\'ve updated the infraction notification channel to {channel.mention}.', ephemeral=True
        )

    @infraction.command(name='time', description='Change the mute time for an infraction.')
    @app_commands.guild_only()
    @app_commands.choices(
        time=[
            app_commands.Choice(name='1 minute', value=60),
            app_commands.Choice(name='5 minutes', value=60 * 5),
            app_commands.Choice(name='30 minutes', value=60 * 30),
            app_commands.Choice(name='1 hour', value=60 * 60),
            app_commands.Choice(name='2 hours', value=60 * 60 * 2),
            app_commands.Choice(name='12 hours', value=60 * 60 * 12),
            app_commands.Choice(name='1 day', value=60 * 60 * 24),
            app_commands.Choice(name='2 days', value=60 * 60 * 24 * 2),
            app_commands.Choice(name='7 days', value=60 * 60 * 24 * 7),
            app_commands.Choice(name='14 days', value=60 * 60 * 24 * 14),
        ],
    )
    async def infraction_time(self, interaction: discord.Interaction, type: InfractionType, time: int) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT * FROM infractions.time WHERE guild_id = $1 AND type = $2) THEN
                        UPDATE infractions.time SET time = $3 WHERE guild_id = $1 AND type = $2
                    ELSE
                        INSERT INTO infractions.time(guild_id, type, time) VALUES($1, $2, $3)
                    END IF;
                END $$
                """,
                interaction.guild.id,
                type.value,
                time,
            )

        return await interaction.response.send_message(
            f'I\'ve updated the total mute time for the {type.name.title()} infraction.', ephemeral=True
        )

    @infraction_moderator.command(name='add', description='Add a moderator to your list of moderators.')
    @app_commands.describe(member='The member to add as a moderator.')
    async def infraction_moderator_add(self, interaction: discord.Interaction, member: discord.Member) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT moderators FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET moderators = array_append(moderators, $2) WHERE guild_id = $1
                    ELSE
                        INSERT INTO infractions.settings(guild_id, moderators) VALUES($1, '{$2}'::bigint[])
                    END IF;
                END $$
                """,
                interaction.guild.id,
                member.id
            )
            
        return await interaction.response.send_message(f'I\'ve added {member.mention} as a moderator.', ephemeral=True)
    
    @infraction_moderator.command(name='remove', description='Remove a moderator to your list of moderators.')
    @app_commands.describe(member='The member to remove as a moderator.')
    async def infraction_moderator_remove(self, interaction: discord.Interaction, member: discord.Member) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT moderators FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET moderators = array_remove(moderators, $2) WHERE guild_id = $1
                    END IF;
                END $$
                """,
                interaction.guild.id,
                member.id
            )
            
        return await interaction.response.send_message(f'I\'ve removed {member.mention} as a moderator.', ephemeral=True)
    
    @infraction_moderator_role.command(name='add', description='Add a moderator role to your list of moderators.')
    @app_commands.describe(role='The role to add as a moderator role.')
    async def infraction_moderator_role_add(self, interaction: discord.Interaction, role: discord.Role) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT moderator_role_ids FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET moderator_role_ids = array_append(moderator_role_ids, $2) WHERE guild_id = $1
                    ELSE
                        INSERT INTO infractions.settings(guild_id, moderator_role_ids) VALUES($1, '{$2}'::bigint[])
                    END IF;
                END $$
                """,
                interaction.guild.id,
                role.id
            )
            
        return await interaction.response.send_message(f'I\'ve added {role.mention} as a moderator role.', ephemeral=True)
    
    @infraction_moderator_role.command(name='remove', description='Remove a moderator role to your list of moderators.')
    @app_commands.describe(member='The role to remove as a moderator role.')
    async def infraction_moderator_role_remove(self, interaction: discord.Interaction, role: discord.Role) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT moderator_role_ids FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET moderator_role_ids = array_remove(moderator_role_ids, $2) WHERE guild_id = $1
                    END IF;
                END $$
                """,
                interaction.guild.id,
                role.id
            )
            
        return await interaction.response.send_message(f'I\'ve removed {role.mention} as a moderator role.', ephemeral=True)

    @infraction_ignored_channels.command(name='add', description='Add an ignored channel to the infraction manager.')
    @app_commands.describe(channel='The channel to add.')
    async def infraction_channels_add(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT ignored_channel_ids FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET ignored_channel_ids = array_append(ignored_channel_ids, $2) WHERE guild_id = $1
                    ELSE
                        INSERT INTO infractions.settings(guild_id, ignored_channel_ids) VALUES($1, '{$2}'::bigint[])
                    END IF;
                END $$
                """,
                interaction.guild.id,
                channel.id
            )
            
        return await interaction.response.send_message(f'I\'ve added {channel.mention} as an ignored channel.', ephemeral=True)
    
    @infraction_ignored_channels.command(name='remove', description='Remove an ignored channel to the infraction manager.')
    @app_commands.describe(channel='The channel to remove.')
    async def infraction_channels_remove(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        assert interaction.guild
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT ignored_channel_ids FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET ignored_channel_ids = array_remove(ignored_channel_ids, $2) WHERE guild_id = $1
                    END IF;
                END $$
                """,
                interaction.guild.id,
                channel.id
            )
            
        return await interaction.response.send_message(f'I\'ve removed {channel.mention} as an ignored channel.', ephemeral=True)
    
    @infraction_allowed_links.command(name='add', description='Add an allowed link to the link filter.')
    @app_commands.describe(link='The link to add.')
    async def infraction_allowed_links_add(self, interaction: discord.Interaction, link: str) -> None:
        assert interaction.guild
        
        if not await self.bot.link_filter.get_links(link):
            return await interaction.response.send_message('I couldn\'t find any links in the `link` parameter you sent...', ephemeral=True)
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT valid_links FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET valid_links = array_append(valid_links, $2) WHERE guild_id = $1
                    ELSE
                        INSERT INTO infractions.settings(guild_id, valid_links) VALUES($1, '{$2}'::bigint[])
                    END IF;
                END $$
                """,
                interaction.guild.id,
                link
            )
            
        return await interaction.response.send_message(f'I\'ve added `{link}` as an allowed link.', ephemeral=True)
        
    @infraction_allowed_links.command(name='remove', description='Remove an allowed link to the link filter.')
    @app_commands.describe(link='The link to remove.')
    async def infraction_allowed_links_remove(self, interaction: discord.Interaction, link: str) -> None:
        assert interaction.guild
        
        if not await self.bot.link_filter.get_links(link):
            return await interaction.response.send_message('I couldn\'t find any links in the `link` parameter you sent...', ephemeral=True)
        
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS(SELECT valid_links FROM infractions.settings WHERE guild_id = $1) THEN
                        UPDATE infractions.settings SET valid_links = array_remove(valid_links, $2) WHERE guild_id = $1
                    END IF;
                END $$
                """,
                interaction.guild.id,
                link
            )
            
        return await interaction.response.send_message(f'I\'ve removed `{link}` as an allowed link.', ephemeral=True)
    
async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Infractions(bot))