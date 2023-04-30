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

from typing import TYPE_CHECKING, List

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, GuildProfanityFinder

from .panel import CreateProfanityFilterPanel, ProfanityPanel

if TYPE_CHECKING:
    from bot import ConnectionType, FuryBot


class Profanity(BaseCog):
    @app_commands.command(
        name='profanity',
        description='The management of a custom profanity filter.',
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    async def profanity(self, interaction: discord.Interaction[FuryBot]) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer()

        # Let's fetch all the data from the database and then spawn the correct panel based on it.
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM profanity.settings WHERE guild_id = $1', interaction.guild_id)

        if not data:
            view = CreateProfanityFilterPanel(target=interaction)
        else:
            # Let's fetch all the automod rules from this guild and get only the ones that are custom profanity filters.
            automod_rule_ids = [row['automod_rule_id'] for row in data]
            all_rules = await interaction.guild.fetch_automod_rules()
            automod_rules = {rule.id: rule for rule in all_rules if rule.id in automod_rule_ids}

            view = ProfanityPanel(rules=automod_rules, target=interaction)

        return await interaction.edit_original_response(view=view, embed=view.embed)

    @commands.Cog.listener('on_automod_rule_create')
    async def on_automod_rule_create(self, rule: discord.AutoModRule):
        if rule.trigger.type is not discord.AutoModRuleTriggerType.keyword:
            return

        # Let's insert this into our DB
        async with self.bot.safe_connection() as connection:
            settings_data = await connection.fetchrow(
                'INSERT INTO profanity.settings (guild_id, automod_rule_id) VALUES ($1, $2) RETURNING *',
                rule.guild.id,
                rule.id,
            )
            assert settings_data

            now = discord.utils.utcnow()
            await connection.executemany(
                'INSERT INTO profanity.words(settings_id, automod_rule_id, word, added_at, guild_id) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (word) DO NOTHING',
                [(settings_data['id'], rule.id, word, now, rule.guild.id) for word in rule.trigger.keyword_filter],
            )

            # Fetch all the words across all the profanity.settings tables where guild_id = rule.guild.id and automod_rule_id != rule.id
            all_words_raw = await connection.fetch(
                'SELECT word FROM profanity.words WHERE automod_rule_id != $1 AND settings_id IN (SELECT id FROM profanity.settings WHERE guild_id = $2)',
                rule.id,
                rule.guild.id,
            )

        all_words = [row['word'] for row in all_words_raw]
        all_words.extend(rule.trigger.keyword_filter)

        # Now we can re-build the profanity finder on our bot instance for this guild.
        pattern = GuildProfanityFinder.create_pattern_from_words(all_words)
        finder = GuildProfanityFinder(pattern, guild_id=rule.guild.id)
        self.bot.add_custom_prodanity_finder(rule.guild.id, finder)

    @commands.Cog.listener('on_automod_rule_delete')
    async def on_automod_rule_delete(self, rule: discord.AutoModRule):
        if rule.trigger.type is not discord.AutoModRuleTriggerType.keyword:
            return

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM profanity.settings WHERE automod_rule_id = $1', rule.id)

            all_words_raw = await connection.fetch(
                'SELECT word FROM profanity.words WHERE settings_id IN (SELECT id FROM profanity.settings WHERE guild_id = $1)',
                rule.guild.id,
            )

        all_words = [row['word'] for row in all_words_raw]
        if all_words:
            pattern = GuildProfanityFinder.create_pattern_from_words(all_words)
            finder = GuildProfanityFinder(pattern, guild_id=rule.guild.id)
            self.bot.add_custom_prodanity_finder(rule.guild.id, finder)
        else:
            # This guild no longer has any custom profanity filters, so we can remove it from our bot instance
            # and go back to the default one.
            self.bot.remove_custom_profanity_finder(rule.guild.id)

    async def _overwrite_words(
        self, settings_id: int, guild_id: int, rule_keywords: List[str], rule_id: int, connection: ConnectionType
    ) -> None:
        all_words = await connection.fetch('SELECT word FROM profanity.words WHERE automod_rule_id = $1', rule_id)

        all_words = [row['word'] for row in all_words]
        words_to_delete = [word for word in all_words if word not in rule_keywords]
        words_to_add = [word for word in rule_keywords if word not in all_words]

        if words_to_delete:
            # Delete all the words to delete
            await connection.execute(
                'DELETE FROM profanity.words WHERE automod_rule_id = $1 AND word = ANY($2::text[])', rule_id, words_to_delete
            )

        if words_to_add:
            await connection.executemany(
                'INSERT INTO profanity.words(settings_id, automod_rule_id, word, added_at, guild_id) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (word) DO NOTHING',
                [(settings_id, rule_id, word, discord.utils.utcnow(), guild_id) for word in words_to_add],
            )

    @commands.Cog.listener('on_automod_rule_update')
    async def on_automod_rule_update(self, rule: discord.AutoModRule):
        if rule.trigger.type is not discord.AutoModRuleTriggerType.keyword:
            return

        rule_keywords = rule.trigger.keyword_filter

        # We need to delete any words from the profanity.words database if the word is not in the new rule keywords.
        # We also need to add any words that are in the new rule keywords but not in the database.
        async with self.bot.safe_connection() as connection:
            settings_id = await connection.fetchval('SELECT id from profanity.settings WHERE automod_rule_id = $1', rule.id)
            if not settings_id:
                # This isn't a tracked item
                return

            await self._overwrite_words(settings_id, rule.guild.id, rule_keywords, rule.id, connection)

            # Now we can fetch all the updated words from the entire guild and re-build the profanity finder.
            all_words_raw = await connection.fetch(
                'SELECT word FROM profanity.words WHERE settings_id IN (SELECT id FROM profanity.settings WHERE guild_id = $1)',
                rule.guild.id,
            )

        all_words = [row['word'] for row in all_words_raw]
        if all_words:
            pattern = GuildProfanityFinder.create_pattern_from_words(all_words)
            finder = GuildProfanityFinder(pattern, guild_id=rule.guild.id)
            self.bot.add_custom_prodanity_finder(rule.guild.id, finder)
        else:
            # This guild no longer has any custom profanity filters, so we can remove it from our bot instance
            # and go back to the default one.
            self.bot.remove_custom_profanity_finder(rule.guild.id)


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Profanity(bot))
