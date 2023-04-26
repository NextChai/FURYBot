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

from typing import TYPE_CHECKING, Dict, List, Union

import discord
from discord import app_commands
from typing_extensions import Self, Unpack

from utils import (
    AfterModal,
    BaseButtonPaginator,
    BaseView,
    BaseViewKwargs,
    ChannelSelect,
    GuildProfanityFinder,
    RoleSelect,
    human_join,
    human_timedelta,
    human_timestamp,
)

if TYPE_CHECKING:
    import asyncpg

    from bot import FuryBot


class ProfanityPaginator(BaseButtonPaginator['asyncpg.Record']):
    async def format_page(self, entries: List[asyncpg.Record]) -> discord.Embed:
        assert self.bot

        embed = self.bot.Embed(
            title=f'Profanity Filter Management - Page {self.current_page} of {self.max_page}',
            description='\n'.join(
                f'- {entry["word"]} (Added {discord.utils.format_dt(entry["added_at"], "R")})' for entry in entries
            ),
        )

        return embed


class CreateProfanityFilterPanel(BaseView):
    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(title='Profanity FIlter Management')

        embed.add_field(
            name='Create New Profanity Filter',
            value='This server does not yet have any custom profanity filters! To create your first one with a default '
            'word set of standard profane terms press "Create Profanity Filter" below.',
            inline=False,
        )

        embed.add_field(
            name='How Does the Profanity Filter Work?',
            value='The bot utilizes [Discord\'s AutoMod](https://support.discord.com/hc/en-us/articles/4421269296535-AutoMod-FAQ) for its profanity filter. '
            'With this system, you will be able to see all profane terms and words in your server settings. Optionally, you can make edits to the '
            'profanity filter in your server settings and it will also update on the bot as well. These updates include changing the custom word set, '
            'deleting, and creating your own custom word set.\n\n'
            'A Discord AutoMod rule can only have 1,000 words, so if you have more than that the bot will manage everything for you. It\'s recommended to '
            'make any changes through the bot rather than your server settings due to the ease of bulk editing across multiple automod rules.',
        )

        return embed

    @discord.ui.button(label='Create Profanity Filter', style=discord.ButtonStyle.success)
    async def create_profanity_filter(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer()

        default_words = await GuildProfanityFinder.get_default_words()

        rule = await interaction.guild.create_automod_rule(
            name='FuryBot Profanity Filter 1',
            event_type=discord.AutoModRuleEventType.message_send,
            trigger=discord.AutoModTrigger(
                type=discord.AutoModRuleTriggerType.keyword,
                keyword_filter=default_words,
            ),
            actions=[
                discord.AutoModRuleAction(
                    custom_message='Your message was blocked due to containing a profane term.',
                )
            ],
        )

        view = ProfanityPanel(rules={rule.id: rule}, target=interaction)
        return await interaction.edit_original_response(view=view, embed=view.embed)


class ManageProfanityTargets(BaseView):
    def __init__(self, rules: Dict[int, discord.AutoModRule], **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.rules: Dict[int, discord.AutoModRule] = rules

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'AutoMod Rule Target and Action Management',
            description='Use the buttons below to manage the AutoMod Rules that contain all the profane terms. '
            'Optionally, you can manage all these in the Discord AutoMod settings, but if you have more than one '
            'AutoMod Rule it can get complicated. This panel affects all the AutoMod rules when you make a change '
            'so you don\'t have to worry about that.',
        )

        rules_names = human_join((rule.name for rule in self.rules.values()))
        embed.add_field(
            name='Automod Rule(s)', value=f'In total, there are **{len(self.rules)}** auto mod rules. {rules_names}'
        )

        for rule in self.rules.values():
            role_channel_mentions = [item.mention for item in [*rule.exempt_roles, *rule.exempt_channels]]

            actions: List[str] = []
            for action in rule.actions:
                if action.type is discord.AutoModRuleActionType.block_message:
                    actions.append(f'╰ Block message: {action.custom_message}')
                elif action.type is discord.AutoModRuleActionType.send_alert_message:
                    actions.append(f'╰ Send alert to <#{action.channel_id}>')
                elif action.type is discord.AutoModRuleActionType.timeout:
                    time_delta = human_timedelta(action.duration.total_seconds()) if action.duration else 'no time.'
                    actions.append(f'╰ Timeout user for {time_delta}')

            actions_display = '\n'.join(actions) if actions else 'No actions.'

            embed.add_field(
                name=rule.name,
                value=f'**Created At*:: {human_timestamp(discord.utils.snowflake_time(rule.id))}\n'
                f'**Exempt Roles and Channels**: {human_join(role_channel_mentions) if role_channel_mentions else "No channels or roles."}\n '
                f'**Actions**: {actions_display}',
            )

        embed.add_field(
            name='What is Syncing?',
            value='Syncing will set all the Automod Allowed targets and actions to the first AutoMod action that was created first. '
            'This means that every AutoMod action will have the same allowed roles or channels. After you sync, you can add and '
            'remove these channels and roles in bulk using the "Add Allowed Targets" and "Remove Allowed Targets" buttons below.',
        )

        return embed

    async def _perform_addition_on_rules(
        self,
        interaction: discord.Interaction[FuryBot],
        targets: Union[List[discord.Role], List[Union[app_commands.AppCommandChannel, app_commands.AppCommandThread]]],
    ) -> None:
        await interaction.response.defer()

        for rule in self.rules.values():
            roles = [target for target in targets if isinstance(target, discord.Role)]
            channels = [
                target
                for target in targets
                if isinstance(target, (app_commands.AppCommandChannel, app_commands.AppCommandThread))
            ]

            allowed_role_ids = list(rule.exempt_role_ids)
            allowed_channel_ids = list(rule.exempt_channel_ids)

            allowed_role_ids.extend(role.id for role in roles)
            allowed_channel_ids.extend(channel.id for channel in channels)

            rule = await rule.edit(
                exempt_roles=[discord.Object(id=role_id) for role_id in allowed_role_ids],
                exempt_channels=[discord.Object(id=channel_id) for channel_id in allowed_channel_ids],
            )
            self.rules[rule.id] = rule

        await interaction.edit_original_response()

    async def _perform_subtraction_on_rules(
        self,
        interaction: discord.Interaction[FuryBot],
        targets: Union[List[discord.Role], List[Union[app_commands.AppCommandChannel, app_commands.AppCommandThread]]],
    ) -> None:
        await interaction.response.defer()

        for rule in self.rules.values():
            roles = [target for target in targets if isinstance(target, discord.Role)]
            channels = [
                target
                for target in targets
                if isinstance(target, (app_commands.AppCommandChannel, app_commands.AppCommandThread))
            ]

            allowed_role_ids = list(rule.exempt_role_ids)
            allowed_channel_ids = list(rule.exempt_channel_ids)

            for role in roles:
                if role.id in allowed_role_ids:
                    allowed_role_ids.remove(role.id)

            for channel in channels:
                if channel.id in allowed_channel_ids:
                    allowed_channel_ids.remove(channel.id)

            rule = await rule.edit(
                exempt_roles=[discord.Object(id=role_id) for role_id in allowed_role_ids],
                exempt_channels=[discord.Object(id=channel_id) for channel_id in allowed_channel_ids],
            )
            self.rules[rule.id] = rule

        await interaction.edit_original_response()

    @discord.ui.button(label='Add Allowed Roles', row=0)
    async def add_allowed_roles(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        RoleSelect(after=self._perform_addition_on_rules, parent=self)

        return await interaction.edit_original_response(view=self)

    @discord.ui.button(label='Remove Allowed Roles', row=0)
    async def remove_allowed_roles(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        RoleSelect(after=self._perform_subtraction_on_rules, parent=self)

        return await interaction.edit_original_response(view=self)

    @discord.ui.button(label='Add Allowed Channels', row=1)
    async def add_allowed_channels(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        ChannelSelect(after=self._perform_addition_on_rules, parent=self)

        return await interaction.edit_original_response(view=self)

    @discord.ui.button(label='Remove Allowed Channels', row=1)
    async def remove_allowed_channels(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        ChannelSelect(after=self._perform_subtraction_on_rules, parent=self)

        return await interaction.edit_original_response(view=self)

    @discord.ui.button(label='Sync', row=2)
    async def sync(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        first_created_rule = sorted(self.rules.values(), key=lambda rule: discord.utils.snowflake_time(rule.id))[0]

        allowed_role_ids = list(first_created_rule.exempt_role_ids)
        allowed_channel_ids = list(first_created_rule.exempt_channel_ids)

        for rule in self.rules.values():
            if rule == first_created_rule:
                continue

            rule = await rule.edit(
                exempt_roles=[discord.Object(id=role_id) for role_id in allowed_role_ids],
                exempt_channels=[discord.Object(id=channel_id) for channel_id in allowed_channel_ids],
            )
            self.rules[rule.id] = rule

        return await interaction.edit_original_response(view=self, embed=self.embed)


class ProfanityPanel(BaseView):
    def __init__(self, rules: Dict[int, discord.AutoModRule], **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.rules: Dict[int, discord.AutoModRule] = rules

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Profanity Filter Management', description='Use the buttons below to manage the custom profanity filter.'
        )

        embed.add_field(
            name='Custom Words Count',
            value=f'Through the **{len(self.rules)} AutoMod Custom Keyword Rules** this server has, there is a '
            f'total of **{len(self.all_words)} words**. You can use the buttons below to add, remove, or view '
            'all the words.',
            inline=False,
        )

        embed.add_field(
            name='Max Words',
            value=f'There is a max of 6 Discord AutoMod Custom Keyword Rules per server, each of which '
            'having a maximum of 1,000 words. This means, in total, you can have a maximum of 6,000 words. You '
            'should not need more than this, but if you do, please contact the developer.',
            inline=False,
        )

        embed.add_field(
            name='Manage Targets',
            value='A target is a channel or role that is exempt from the profanity filter. This means that '
            'the profanity filter will not apply to messages sent in the target channel or by the target role. '
            'To bulk edit these across all your AutoMod Custom Keyword Rules, use the "Manage Targets" button '
            'below.',
            inline=False,
        )

        return embed

    @property
    def all_words(self) -> List[str]:
        all_words: List[str] = []

        for rule in self.rules.values():
            all_words.extend(rule.trigger.keyword_filter)

        return all_words

    async def _add_words_after(
        self, interaction: discord.Interaction[FuryBot], words_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        assert interaction.guild
        await interaction.response.defer()

        words = [word.strip() for word in words_input.value.split(',')]

        # Let's go through the rules and find ones that can hold any words
        for rule in self.rules.values():
            existing_keywords = rule.trigger.keyword_filter

            if len(existing_keywords) == 1_000:
                # This filter is maxxed
                continue

            total_keywords_available = 1_000 - len(existing_keywords)

            # Let's get the words that can fit in this rule
            words_to_insert = words[:total_keywords_available]

            # We can remove these from the list of words to insert
            words = words[total_keywords_available:]

            # Now we can edit the automod rule and add these words
            rule = await rule.edit(trigger=discord.AutoModTrigger(keyword_filter=existing_keywords + words_to_insert))
            self.rules[rule.id] = rule

        if words:
            # We need to create a new rule and add the remaining words
            for chunk in discord.utils.as_chunks(words, 1_000):
                rule_number = len(self.rules) + 1
                rule = await interaction.guild.create_automod_rule(
                    name=f'FuryBot Profanity Filter {rule_number}',
                    event_type=discord.AutoModRuleEventType.message_send,
                    trigger=discord.AutoModTrigger(
                        type=discord.AutoModRuleTriggerType.keyword,
                        keyword_filter=chunk,
                    ),
                    actions=[
                        discord.AutoModRuleAction(
                            custom_message='Your message was blocked due to containing a profane term.',
                        )
                    ],
                )
                self.rules[rule.id] = rule

        await interaction.followup.send(f'Added a total of {len(words)} words to the profanity filter.', ephemeral=True)
        return await interaction.edit_original_response(embed=self.embed)

    @discord.ui.button(label='Add Words')
    async def add_words(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        modal = AfterModal(
            self.bot,
            self._add_words_after,
            discord.ui.TextInput(
                label='Words',
                placeholder='Enter the words you want to add, separated by commas. "one, two, three".',
                style=discord.TextStyle.long,
            ),
            title='Add Profane Words',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)

    async def _remove_words_after(
        self, interaction: discord.Interaction[FuryBot], words_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        assert interaction.guild
        await interaction.response.defer()

        words = [word.strip() for word in words_input.value.split(',')]

        for rule in self.rules.values():
            existing_keywords = rule.trigger.keyword_filter

            # Let's remove any words from the existing_keywords that share common words with the words we want to remove
            existing_keywords_to_remove = [word for word in existing_keywords if word in words]

            if not existing_keywords_to_remove:
                continue

            # Now we can remove these words from the existing_keywords
            new_existing_keywords = [word for word in existing_keywords if word not in existing_keywords_to_remove]

            rule = await rule.edit(trigger=discord.AutoModTrigger(keyword_filter=new_existing_keywords))
            self.rules[rule.id] = rule

        await interaction.followup.send(f'Removed a total of {len(words)} words from the profanity filter.', ephemeral=True)
        return await interaction.edit_original_response(embed=self.embed)

    @discord.ui.button(label='Remove Words')
    async def remove_word(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        modal = AfterModal(
            self.bot,
            self._remove_words_after,
            discord.ui.TextInput(
                label='Words', placeholder='Enter the words you want to remove.', style=discord.TextStyle.long
            ),
            title='Remove Profane Words',
            timeout=None,
        )
        return await interaction.response.send_modal(modal)

    @discord.ui.button(label='View All Words')
    async def view_all_words(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer(thinking=True, ephemeral=True)

        async with self.bot.safe_connection() as connection:
            all_words = await connection.fetch('SELECT * FROM profanity.words WHERE guild_id = $1', interaction.guild_id)

        paginator = ProfanityPaginator(entries=all_words, per_page=20, target=interaction)

        embed = await paginator.embed()
        return await interaction.edit_original_response(embed=embed, view=paginator)

    @discord.ui.button(label='Manage Targets')
    async def manage_rules(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        view = self.create_child(ManageProfanityTargets, rules=self.rules)
        return await interaction.edit_original_response(embed=view.embed, view=view)
