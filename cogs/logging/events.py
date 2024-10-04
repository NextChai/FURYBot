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

import functools
from typing import TYPE_CHECKING, Any, Callable, Concatenate, Coroutine, List, Optional, ParamSpec, Tuple, TypeVar

import discord

from utils import BaseCog, human_join, human_timedelta

T = TypeVar('T')
P = ParamSpec('P')

if TYPE_CHECKING:
    from .settings import LoggingSettings

__all__: Tuple[str, ...] = ('LoggingEventsCog', 'logging_event')


def logging_event(
    func: Callable[
        Concatenate[LoggingEventsCog, P],
        Coroutine[Any, Any, Tuple[Optional[int], Optional[discord.Embed]]],
    ]
):
    """
    Marks a function as a logging event. Will take the event, get the logging settings,
    then get the embed from the logger and send it to the settings, if applicable.
    """

    @functools.wraps(func)
    async def inner(self: LoggingEventsCog, *args: P.args, **kwargs: P.kwargs) -> None:
        guild_id, embed = await func(self, *args, **kwargs)
        if embed is None or guild_id is None:
            return

        settings: Optional[LoggingSettings] = self.bot.get_logging_settings(guild_id)
        if settings is None:
            return

        channel = settings.logging_channel
        if channel is None:
            # This channel has been deleted, we can ignore this.
            return

        logging_webhook = settings.logging_webhook
        if logging_webhook is None:
            return

        await logging_webhook.send(
            embed=embed, username=self.bot.user.display_name, avatar_url=self.bot.user.display_avatar.url
        )

    return inner


class LoggingEventsCog(BaseCog):

    @staticmethod
    def _automod_trigger_metadata(trigger: discord.AutoModTrigger) -> List[str]:
        meta: List[str] = [
            f'Type: {trigger.type.name.replace("_", " ").title()}',
        ]

        if trigger.allow_list:
            meta.append(f'Allow List: {human_join(trigger.allow_list)}')
        if trigger.keyword_filter:
            meta.append(f'Block List: {human_join(trigger.keyword_filter)}')
        if trigger.mention_limit:
            meta.append(f'Mention Limit: {trigger.mention_limit} mentions.')
        if trigger.mention_raid_protection:
            meta.append('Raid Protection is enabled.')
        if trigger.regex_patterns:
            meta.append(
                f'Regex Patterns: {human_join((f"`{pattern}`" for pattern in trigger.regex_patterns), delimiter="|")}'
            )

        return meta

    @staticmethod
    def _automod_actions_metadata(actions: List[discord.AutoModRuleAction]) -> List[str]:
        actions_fmt: List[str] = []
        for action in actions:
            extra: List[str] = []
            if action.channel_id:
                extra.append(f'Channel <#{action.channel_id}>')

            if action.duration:
                extra.append(f'For {human_timedelta(action.duration.total_seconds())} seconds')

            if action.custom_message:
                extra.append(f'With message "{action.custom_message}"')

            actions_fmt.append(
                f'**{action.type.name.replace("_", " ").title()}**: {human_join(extra, delimiter="|") or "No extra info."}'
            )

        return actions_fmt

    def _embed_from_automod_rule(self, rule: discord.AutoModRule) -> discord.Embed:
        status = 'active' if rule.enabled else 'inactive'
        activation = (
            'a message is sent' if rule.event_type is discord.AutoModRuleEventType else 'a user updates their profile'
        )

        embed = self.bot.Embed(
            title=f'Automod Rule "{rule.name}"',
            description=(
                f'This rule has been created by <@{rule.creator_id}>. This new rule is currently **{status}**. '
                f'It will trigger when **{activation}**.'
            ),
        )

        if rule.exempt_roles:
            roles = human_join((role.mention for role in rule.exempt_roles))
            embed.add_field(name='Exempt Roles', value=roles, inline=False)

        if rule.exempt_channels:
            channels = human_join((channel.mention for channel in rule.exempt_channels))
            embed.add_field(name='Exempt Channels', value=channels, inline=False)

        actions_fmt: List[str] = self._automod_actions_metadata(rule.actions)
        if actions_fmt:
            embed.add_field(name='Actions', value='\n'.join(actions_fmt), inline=False)

        trigger_meta: List[str] = self._automod_trigger_metadata(rule.trigger)
        if trigger_meta:
            # We need to ensure that adding this to the description wouldn't set it over the
            # 6000 character limit.
            joined = '\n'.join(trigger_meta)
            trigger_meta_formatted = f'\n\n**Trigger Metadata**:\n{joined}'
            if len(embed) + len(trigger_meta_formatted) < 6000 and embed.description:
                embed.description += trigger_meta_formatted

        return embed

    @logging_event
    async def on_automod_rule_create(self, rule: discord.AutoModRule) -> Tuple[Optional[int], Optional[discord.Embed]]:
        embed = self._embed_from_automod_rule(rule)
        embed.color = discord.Color.green()
        if embed.title:  # Simply to make type checker happy
            embed.title += ' Created'

        return (rule.guild.id, embed)

    @logging_event
    async def on_automod_rule_update(self, rule: discord.AutoModRule) -> Tuple[Optional[int], Optional[discord.Embed]]:
        embed = self._embed_from_automod_rule(rule)
        embed.color = discord.Color.orange()
        if embed.title:
            embed.title += ' Updated'

        return (rule.guild.id, embed)

    @logging_event
    async def on_automod_rule_delete(self, rule: discord.AutoModRule) -> Tuple[Optional[int], Optional[discord.Embed]]:
        embed = self._embed_from_automod_rule(rule)
        embed.color = discord.Color.red()
        if embed.title:
            embed.title += ' Deleted'

        return (rule.guild.id, embed)

    @logging_event
    async def on_automod_action(self, execution: discord.AutoModAction) -> Tuple[Optional[int], Optional[discord.Embed]]:
        embed = self.bot.Embed(
            title='Automod Action',
            description=f'An action has been taken against <@{execution.user_id}> in <#{execution.channel_id}>.',
        )

        # The action that was taken
        action = execution.action
        actions_taken: List[str] = [
            f'**Type**: {action.type.name.replace("_", " ").title()}',
        ]

        if action.duration:
            actions_taken.append(f'**Duration**: {human_timedelta(action.duration.total_seconds())} seconds')
        if action.custom_message:
            actions_taken.append(f'**Message**: {action.custom_message}')

        embed.add_field(name='Action Taken', value='\n'.join(actions_taken), inline=False)
        embed.add_field(name='Content Trigger', value=execution.content, inline=False)

        if execution.matched_keyword:
            embed.add_field(name='Matched Keyword', value=execution.matched_keyword, inline=False)

        if execution.matched_content:
            embed.add_field(name='Matched Content', value=execution.matched_content, inline=False)

        return (execution.guild_id, embed)

    def _embed_from_guild_channel(self, channel: discord.abc.GuildChannel) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'Channel {channel.name} {channel.type.name.title()}',
        )

        return embed

    @logging_event
    async def on_guild_channel_delete(
        self,
        channel: discord.abc.GuildChannel,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_channel_create(
        self,
        channel: discord.abc.GuildChannel,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_update(
        self, before: discord.Guild, after: discord.Guild
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: List[discord.Emoji],
        after: List[discord.Emoji],
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: List[discord.Sticker],
        after: List[discord.Sticker],
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_audit_log_entry_create(
        self, entry: discord.AuditLogEntry
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_invite_create(self, invite: discord.Invite) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_invite_delete(self, invite: discord.Invite) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_member_join(self, member: discord.Member) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_member_remove(self, member: discord.Member) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_user_update(
        self,
        before: discord.User,
        after: discord.User,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_member_ban(
        self, guild: discord.Guild, user: discord.User
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_member_unban(
        self,
        guild: discord.Guild,
        user: discord.User,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_presence_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_message_edit(
        self,
        payload: discord.RawMessageUpdateEvent,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_message_delete(
        self,
        payload: discord.RawMessageDeleteEvent,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_poll_vote_add(
        self, payload: discord.RawPollVoteActionEvent
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_poll_vote_remove(
        self, payload: discord.RawPollVoteActionEvent
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_raw_reaction_clear(
        self, payload: discord.RawReactionClearEvent
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_reaction_clear_emoji(self, reaction: discord.Reaction) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_role_create(self, role: discord.Role) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_role_delete(self, role: discord.Role) -> Tuple[Optional[int], Optional[discord.Embed]]: ...

    @logging_event
    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> Tuple[Optional[int], Optional[discord.Embed]]: ...
