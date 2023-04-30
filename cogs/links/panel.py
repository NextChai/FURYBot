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

import discord
from typing_extensions import Self, Unpack

from utils import BaseButtonPaginator, BaseView, BaseViewKwargs, SelectOneOfMany, human_timedelta, ShortTime, AfterModal

from .settings import *


class CreateLinkSettings(BaseView):
    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(title='Create Link Filtering')
        embed.add_field(
            name='What is Link Filtering?',
            value='It is effortless for members to post inappropriate links in a standard Discord server, '
            'but have no fear because Link Filtering is here! With link filtering, you can limit all links '
            'sent to your Discord server and only allow specific links/domains. This ensures all content being '
            'posted to your Discord server is PG for a school environment.',
            inline=False,
        )

        embed.add_field(
            name='How do I Setup Link Filtering?',
            value='Press the "Create Link Filtering" button below and the bot will prepare everything! '
            'From there, you can choose which links/domains you want to be allowed and the '
            'consequences of a member posting an unauthorized link. ',
            inline=False,
        )

        embed.add_field(
            name='Can I Delete Link FIltering After It\'s Created?',
            value='Absolutely! If you create a link filter and then, later on, decide you want to remove it, '
            'that is totally ok! A "Delete" button has been provided for you.',
            inline=False,
        )

        return embed

    @discord.ui.button(label='Create Link Filtering', style=discord.ButtonStyle.green)
    async def create_link_filtering(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        assert interaction.guild

        await interaction.response.defer()

        async with self.bot.safe_connection() as connection:
            settings = await LinkSettings.create(
                bot=self.bot,
                connection=connection,
                guild_id=interaction.guild.id,
            )

        view = ManageLinkSettings(settings=settings, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)


class ManageLinkActions(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Link Filtering Actions',
            description='Use the buttons below to add or remove the actions the bot takes '
            'when a link is posted to an unauthorized channel or by an unauthorized role.',
        )

        for action in self.settings.actions:
            value: str
            if action.type is LinkActionType.mute:
                assert action.delta
                value = f'╰ Mute author for {human_timedelta(action.delta.total_seconds())}'
            elif action.type is LinkActionType.surpress:
                value = '╰ Surpress (delete) the message.'
            elif action.type is LinkActionType.warn:
                value = f'╰ Warn the author: "{action.warn_message}"'
            else:
                raise NotImplementedError

            embed.add_field(name=action.type.name.title(), value=value, inline=False)

        if not embed.fields:
            embed.add_field(name='Add a First Action', value='Use the "Add Action" button below to add your first action.')

        return embed

    async def _add_mute_action_after(
        self, interaction: discord.Interaction[FuryBot], delta_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        # We need to try and convert the delta to something we can use...
        short_time_re = ShortTime.compiled
        match = short_time_re.match(delta_input.value)

        if not match:
            await interaction.followup.send(
                f'Invalid time format. Please try again.',
                ephemeral=True,
            )
            return await interaction.edit_original_response(view=self, embed=self.embed)

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        data.pop('years', None)
        data.pop('months', None)

        time = datetime.timedelta(**data)

        if time > datetime.timedelta(days=28):
            await interaction.followup.send(
                f'Time must be less than 28 days.',
                ephemeral=True,
            )
            return await interaction.edit_original_response(view=self, embed=self.embed)

        async with self.bot.safe_connection() as connection:
            await self.settings.create_link_action(connection=connection, type=LinkActionType.mute, delta=time)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    async def _add_warn_action_after(
        self, interaction: discord.Interaction[FuryBot], message_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        async with self.bot.safe_connection() as connection:
            await self.settings.create_link_action(
                connection=connection, type=LinkActionType.warn, warn_message=message_input.value
            )

        return await interaction.edit_original_response(view=self, embed=self.embed)

    async def _add_action_after(
        self, interaction: discord.Interaction[FuryBot], action_types: List[str]
    ) -> Optional[discord.InteractionMessage]:
        action_type = LinkActionType(action_types[0])

        if action_type is LinkActionType.surpress:
            await interaction.response.defer()

            async with self.bot.safe_connection() as connection:
                await self.settings.create_link_action(connection=connection, type=action_type)

            return await interaction.edit_original_response(embed=self.embed, view=self)
        elif action_type is LinkActionType.mute:
            # We need to launch a model for this.
            modal = AfterModal(
                self.bot,
                self._add_mute_action_after,
                discord.ui.TextInput(
                    label='Enter The Duration', placeholder='Enter the duration of mute.. for ex: "5 minutes 30 seconds"'
                ),
                timeout=None,
                title='Mute Action',
            )
            return await interaction.response.send_modal(modal)
        elif action_type is LinkActionType.warn:
            modal = AfterModal(
                self.bot,
                self._add_warn_action_after,
                discord.ui.TextInput(label='Enter Warning Message', placeholder='Enter the warning message to send...'),
                title='Warn Action',
                timeout=None,
            )
            return await interaction.response.send_modal(modal)
        else:
            raise NotImplementedError('Did not IMPL new link action type.')

    @discord.ui.button(label='Add Action')
    async def add_action(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        SelectOneOfMany(
            self,
            options=[discord.SelectOption(label=type.name.title(), value=type.value) for type in LinkActionType],
            after=self._add_action_after,
            placeholder='Select an action type to add...',
        )

        return await interaction.edit_original_response(view=self)

    async def _remove_action_after(
        self, interaction: discord.Interaction[FuryBot], action_type_values: List[str]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        action_types = [LinkActionType(action_type) for action_type in action_type_values]

        to_delete: List[LinkAction] = []
        for action in self.settings.actions:
            if action.type in action_types:
                to_delete.append(action)

        if to_delete:
            async with self.bot.safe_connection() as connection:
                for action in to_delete:
                    await action.delete(connection=connection)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Action')
    async def remove_action(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        SelectOneOfMany(
            self,
            options=[discord.SelectOption(label=type.name.title(), value=type.value) for type in LinkActionType],
            after=self._add_action_after,
            placeholder='Select an action type to remove...',
        )

        return await interaction.edit_original_response(view=self)


class AllowedItemPaginator(BaseButtonPaginator['AllowedLink']):
    ...


class ManageAllowedItems(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Link Filtering Allowed Items',
            description='Use the buttons below to add and remove allowed domains or links '
            'that are bypassed by the link finder.',
        )

        embed.add_field(
            name='Allowed Items',
            value=f'Use the buttons below to manage your {len(self.settings.allowed_links)} allowed items. '
            'Use the "View Allowed Items" button to see all your allowed domains and links for this link filter.',
        )

        return embed

    @discord.ui.button(label='Add Allowed Item')
    async def add_allowed_item(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='Remove Allowed Item')
    async def remove_allowed_item(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='View Allowed Items')
    async def view_allowed_items(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        paginator = self.create_child(AllowedItemPaginator, entries=self.settings.allowed_links, per_page=20)
        return await interaction.edit_original_response(embed=paginator.embed, view=paginator)


class ManageExemptTargets(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings
        raise NotImplementedError

    @property
    def embed(self) -> discord.Embed:
        ...

    @discord.ui.button(label='Add Exempt Targets')
    async def add_exempt_targets(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        ...

    @discord.ui.button(label='Remove Exempt Targets')
    async def remove_exempt_targets(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        ...


class ManageLinkSettings(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Link Filtering Settings', description='Use the buttons below to manage your link filtering settings.'
        )

        # Let's get the current ctions and words from these settings.
        embed.add_field(
            name='Allowed Items',
            value=f'There is **{len(self.settings.allowed_links)}** allowed '
            'items for link filtering. Click the button below to manage them.',
            inline=False,
        )

        actions_display: List[str] = []
        for action in self.settings.actions:
            if action.type is LinkActionType.mute:
                assert action.delta
                actions_display.append(f'╰ Mute author for {human_timedelta(action.delta.total_seconds())}')
            elif action.type is LinkActionType.surpress:
                actions_display.append('╰ Surpress (delete) the message.')
            elif action.type is LinkActionType.warn:
                actions_display.append(f'╰ Warn the author: "{action.warn_message}"')

        actions = f'On a link sent to your Discord server, the bot will take the following action(s):\n'
        if actions_display:
            actions += "\n".join(actions_display)
        else:
            actions += "╰ No actions will be taken."

        embed.add_field(
            name='Actions',
            value=actions,
            inline=False,
        )

        return embed

    @discord.ui.button(label='Manage Allowed Items')
    async def manage_allowed_targets(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        view = self.create_child(ManageAllowedItems, settings=self.settings)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @discord.ui.button(label='Manage Actions')
    async def manage_actions(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        view = self.create_child(ManageLinkActions, settings=self.settings)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @discord.ui.button(label='Delete Filter')
    async def delete_filter(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...
