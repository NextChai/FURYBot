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

import datetime
import enum
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from utils import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot


class InfractionType(enum.Enum):
    links = 'Links'
    profanity = 'Profanity'


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
        parent=infraction,
    )

    infraction_moderator_role = app_commands.Group(
        name='moderator_role',
        description='Manage infraction moderator roles.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
        parent=infraction,
    )

    infraction_allowed_link = app_commands.Group(
        name='allowed_link',
        description='Add and remove allowed links.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
        parent=infraction,
    )

    infraction_ignored_channel = app_commands.Group(
        name='ignored_channel',
        description='Manage ignored channels for the infraction manager.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
        parent=infraction,
    )

    infraction_profanity = app_commands.Group(
        name='profanity',
        description='Manage the profanity filter.',
        default_permissions=discord.Permissions(moderate_members=True),
        guild_only=True,
        parent=infraction,
    )

    @infraction.command(name='notification_channel', description='Change the notification channel for infractions.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    @app_commands.describe(channel='The channel to set for notifications.')
    async def infraction_channel(self, interaction: discord.Interaction[FuryBot], channel: discord.TextChannel) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO infractions.settings(guild_id, notification_channel_id) VALUES($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET notification_channel_id = EXCLUDED.notification_channel_id
                """,
                interaction.guild.id,
                channel.id,
            )

        return await interaction.response.send_message(
            f'I\'ve updated the infraction notification channel to {channel.mention}.', ephemeral=True
        )

    @infraction.command(name='time', description='Change the mute time for an infraction.')
    @app_commands.guild_only()
    @app_commands.describe(time='The total time to mute when an infraction occurrs.')
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
    async def infraction_time(self, interaction: discord.Interaction[FuryBot], type: InfractionType, time: int) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            # Edit singular profanity check
            if type is InfractionType.profanity:
                rule_id = await connection.fetchval(
                    'SELECT automod_rule_id FROM infractions.profaniy WHERE guild_id = $1', interaction.guild.id
                )
                if not rule_id:
                    return await interaction.response.send_message('You have no profanity filter.', ephemeral=True)

                try:
                    rule = await interaction.guild.fetch_automod_rule(rule_id)
                except discord.NotFound:
                    return await interaction.response.send_message(
                        'A mod deleted the profanity filter automod rule. I could not edit it.', ephemeral=True
                    )

                if not rule.actions:
                    return await interaction.response.send_message(
                        'A moderator has edited this automod rule. I can not do anything to it now.', ephemeral=True
                    )

                action = rule.actions[0]
                action.duration = datetime.timedelta(seconds=time)
                await rule.edit(actions=[action])
                return await interaction.response.send_message('I\'ve updated the time.')

            # NOTE: A singular query here gets mad because of how asyncpg handles parameters.
            data = await connection.fetchrow(
                'SELECT * FROM infractions.time WHERE guild_id = $1 AND type = $2', interaction.guild.id, type.value
            )
            if data:
                await connection.execute(
                    'UPDATE infractions.time SET time = $3 WHERE guild_id = $1 AND type = $2',
                    interaction.guild.id,
                    type.value,
                    time,
                )
            else:
                await connection.execute(
                    'INSERT INTO infractions.time(guild_id, type, time) VALUES($1, $2, $3)',
                    interaction.guild.id,
                    type.value,
                    time,
                )

        return await interaction.response.send_message(
            f'I\'ve updated the total mute time for the {type.name.title()} infraction.', ephemeral=True
        )

    @infraction_moderator.command(name='add', description='Add a moderator to your list of moderators.')
    @app_commands.describe(member='The member to add as a moderator.')
    async def infraction_moderator_add(self, interaction: discord.Interaction[FuryBot], member: discord.Member) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO infractions.settings(guild_id, moderators) VALUES($1, ARRAY[ $2 ]::BIGINT[])
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET moderators = array_append((SELECT moderators FROM infractions.settings WHERE guild_id = $1), $2)
                """,
                interaction.guild.id,
                member.id,
            )

        return await interaction.response.send_message(f'I\'ve added {member.mention} as a moderator.', ephemeral=True)

    @infraction_moderator.command(name='remove', description='Remove a moderator to your list of moderators.')
    @app_commands.describe(member='The member to remove as a moderator.')
    async def infraction_moderator_remove(self, interaction: discord.Interaction[FuryBot], member: discord.Member) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                UPDATE infractions.settings SET moderators = array_remove(moderators, $2) WHERE guild_id = $1
                """,
                interaction.guild.id,
                member.id,
            )

        return await interaction.response.send_message(f'I\'ve removed {member.mention} as a moderator.', ephemeral=True)

    @infraction_moderator_role.command(name='add', description='Add a moderator role to your list of moderators.')
    @app_commands.describe(role='The role to add as a moderator role.')
    async def infraction_moderator_role_add(self, interaction: discord.Interaction[FuryBot], role: discord.Role) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO infractions.settings(guild_id, moderator_role_ids) VALUES($1, ARRAY[ $2 ]::BIGINT[])
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET moderator_role_ids = array_append((SELECT moderator_role_ids FROM infractions.settings WHERE guild_id = $1), $2)
                """,
                interaction.guild.id,
                role.id,
            )

        return await interaction.response.send_message(f'I\'ve added {role.mention} as a moderator role.', ephemeral=True)

    @infraction_moderator_role.command(name='remove', description='Remove a moderator role to your list of moderators.')
    @app_commands.describe(role='The role to remove as a moderator role.')
    async def infraction_moderator_role_remove(self, interaction: discord.Interaction[FuryBot], role: discord.Role) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                UPDATE infractions.settings SET moderator_role_ids = array_remove(moderator_role_ids, $2) WHERE guild_id = $1
                """,
                interaction.guild.id,
                role.id,
            )

        return await interaction.response.send_message(f'I\'ve removed {role.mention} as a moderator role.', ephemeral=True)

    @infraction_ignored_channel.command(name='add', description='Add an ignored channel to the infraction manager.')
    @app_commands.describe(channel='The channel to add.')
    async def infraction_ignored_channel_add(
        self, interaction: discord.Interaction[FuryBot], channel: discord.TextChannel
    ) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO infractions.settings(guild_id, ignored_channel_ids) VALUES($1, ARRAY[ $2 ]::BIGINT[])
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET ignored_channel_ids = array_append((SELECT ignored_channel_ids FROM infractions.settings WHERE guild_id = $1), $2)
                """,
                interaction.guild.id,
                channel.id,
            )

        return await interaction.response.send_message(
            f'I\'ve added {channel.mention} as an ignored channel.', ephemeral=True
        )

    @infraction_ignored_channel.command(name='remove', description='Remove an ignored channel to the infraction manager.')
    @app_commands.describe(channel='The channel to remove.')
    async def infraction_ignored_channel_remove(
        self, interaction: discord.Interaction[FuryBot], channel: discord.TextChannel
    ) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                UPDATE infractions.settings SET ignored_channel_ids = array_remove(ignored_channel_ids, $2) WHERE guild_id = $1
                """,
                interaction.guild.id,
                channel.id,
            )

        return await interaction.response.send_message(
            f'I\'ve removed {channel.mention} as an ignored channel.', ephemeral=True
        )

    @infraction_allowed_link.command(name='add', description='Add a link to the link filter.')
    @app_commands.describe(link='The link to add.')
    async def infraction_allowed_link_add(self, interaction: discord.Interaction[FuryBot], link: str) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                INSERT INTO infractions.settings(guild_id, valid_links) VALUES($1, ARRAY[ $2 ]::TEXT[])
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET valid_links = array_append((SELECT valid_links FROM infractions.settings WHERE guild_id = $1), $2)
                """,
                interaction.guild.id,
                link,
            )

        self.bot.link_filter._allowed_links.pop(interaction.guild.id, None)
        return await interaction.response.send_message(f'I\'ve added `{link}` as an allowed link.', ephemeral=True)

    @infraction_allowed_link.command(name='remove', description='The link to remove from the link filter.')
    @app_commands.describe(link='The link to remove.')
    async def infraction_allowed_link_remove(self, interaction: discord.Interaction[FuryBot], link: str) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                """
                UPDATE infractions.settings SET valid_links = array_remove(valid_links, $2) WHERE guild_id = $1
                """,
                interaction.guild.id,
                link,
            )

        self.bot.link_filter._allowed_links.pop(interaction.guild.id, None)
        return await interaction.response.send_message(f'I\'ve removed `{link}` as an allowed link.', ephemeral=True)

    @infraction_profanity.command(name='add', description='Add a term to the profanity filter.')
    @app_commands.describe(term='The term to add.')
    async def infraction_profanity_add(self, interaction: discord.Interaction[FuryBot], term: str) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM infractions.profanity WHERE guild_id = $1', interaction.guild.id)

            if data:
                automod_rule_id = data['automod_rule_id']
                try:
                    automod_rule = await interaction.guild.fetch_automod_rule(automod_rule_id)
                except discord.NotFound:
                    pass
                else:
                    wordset = automod_rule.trigger.keyword_filter
                    wordset.append(term)
                    await automod_rule.edit(trigger=automod_rule.trigger)
                    return await interaction.response.send_message(
                        f'Added `{term}` to the profanity filter.', ephemeral=True
                    )

            await interaction.response.defer(ephemeral=True)

            settings = await connection.fetchrow(
                'SELECT * FROM infractions.settings WHERE guild_id = $1', interaction.guild.id
            )
            settings = dict(settings) if settings else {}

            word_data = await connection.fetch('SELECT word FROM profane_words')
            words = [entry['word'] for entry in word_data]
            if term not in words:
                words.append(term)

            automod_rule = await interaction.guild.create_automod_rule(
                name='FuryBot Profanity',
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.keyword,
                    keyword_filter=words,
                ),
                actions=[
                    discord.AutoModRuleAction(
                        channel_id=settings.get('notification_channel_id'), duration=datetime.timedelta(minutes=5)
                    )
                ],
                exempt_channels=[discord.Object(id=channel_id) for channel_id in settings.get('ignored_channel_ids', [])],
                exempt_roles=[discord.Object(id=role_id) for role_id in settings.get('moderator_role_ids', [])],
            )

            await connection.execute(
                """
                INSERT INTO infractions.profanity(guild_id, automod_rule_id) VALUES($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE
                    SET automod_rule_id = EXCLUDED.automod_rule_id
                """,
                interaction.guild.id,
                automod_rule.id,
            )

        await interaction.edit_original_response(
            content=f'Done. I\'ve created a new profanity filter for you and added the term `{term}`.'
        )

    @infraction_profanity.command(name='remove', description='Remove a word to the profanity filter.')
    @app_commands.describe(term='The term to remove.')
    async def infraction_profanity_remove(self, interaction: discord.Interaction[FuryBot], term: str) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM infractions.profanity WHERE guild_id = $1', interaction.guild.id)

        if not data:
            return await interaction.response.send_message('There is no profanity filter to remove the term from.')

        automod_rule_id = data['automod_rule_id']
        try:
            automod_rule = await interaction.guild.fetch_automod_rule(automod_rule_id)
        except discord.NotFound:
            return await interaction.response.send_message('This automod rule was deleted.')

        wordset = automod_rule.trigger.keyword_filter
        if term not in wordset:
            return await interaction.response.send_message(f'The term `{term}` is not profane.', ephemeral=True)

        wordset.remove(term)
        await automod_rule.edit(trigger=automod_rule.trigger)
        return await interaction.response.send_message(f'Removed `{term}` from the profanity filter.', ephemeral=True)

    @app_commands.command(name='get_links', description='Get the links from a given text.')
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(phrase='The phradiscord.Interaction[FuryBot]ks.')
    @app_commands.guild_only()
    async def get_links(self, interaction: discord.Interaction[FuryBot], phrase: str) -> None:
        assert interaction.guild

        links = await self.bot.link_filter.get_links(phrase, guild_id=interaction.guild.id)
        return await interaction.response.send_message(
            '**Links found**:\n\n' + '\n'.join(f'- <{link}>' for link in links or ['No links found.']), ephemeral=True
        )


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Infractions(bot))
