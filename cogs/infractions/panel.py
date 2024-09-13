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
import functools
from typing import TYPE_CHECKING, List, Union, cast

import discord
from discord import app_commands
from typing_extensions import Self, Unpack

from utils import BaseView, BaseViewKwargs, ChannelSelect, RoleSelect, UserSelect, human_join, ConfirmationGetter

if TYPE_CHECKING:
    from bot import FuryBot

    from .settings import InfractionsSettings


class ModeratorEditAction(enum.Enum):
    ADD = 'add'
    REMOVE = 'remove'


class DoesWantToCreateInfractionsSettings(BaseView):
    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)

        ConfirmationGetter(
            after=self._handle_response,
            parent=self,
        )

    @property
    def embed(self) -> discord.Embed:
        return self.bot.Embed(
            title='Infraction Settings Creation',
            description='Would you like to create infraction settings for this server? Infraction settings dictate some of the behavior of the infraction system.',
        )

    async def _handle_response(
        self, interaction: discord.Interaction[FuryBot], should_create: bool
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        guild_id = interaction.guild_id
        assert guild_id is not None

        if should_create:
            settings = await InfractionsSettings.create(guild_id, bot=self.bot)
            panel = InfractionsSettingsPanel(settings, target=interaction)

            return await interaction.edit_original_response(embed=panel.embed, view=panel)

        return await interaction.edit_original_response(content='Infractions settings creation cancelled.')


class InfractionsSettingsPanel(BaseView):
    def __init__(self, settings: InfractionsSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: InfractionsSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Infraction Settings',
            description='Use the buttons below to manage the infraction settings for the server. These settings dictate some of the behavior of the infraction system.',
        )

        settings = self.settings

        channel = settings.notification_channel
        if channel:
            embed.add_field(
                name='Infraction Notification Channel',
                value=f'The channel that infraction notifications go to.\n**Assigned as**: {channel.mention}',
                inline=False,
            )
        else:
            embed.add_field(
                name='Infraction Notification Channel',
                value=(
                    'No channel set. Use the button below to assign one.'
                    if settings.notification_channel_id is None
                    else 'Channel not found. Was it deleted? Use the button below to reassign one.'
                ),
                inline=False,
            )

        moderator_ids = settings.moderator_ids
        if moderator_ids:
            mod_mentions = human_join((f'<@{mod_id}>' for mod_id in moderator_ids))
            embed.add_field(
                name='Moderators',
                value=f'The users that are not affected by the infraction system.\n{mod_mentions}',
                inline=False,
            )
        else:
            embed.add_field(
                name='Moderators',
                value='No moderators set. Moderators are users that are not affected by the infraction system. Use the buttons below to add some.',
                inline=False,
            )

        moderator_role_ids = settings.moderator_role_ids
        if moderator_role_ids:
            role_mentions = human_join((f'<@&{role_id}>' for role_id in moderator_role_ids))
            embed.add_field(
                name='Moderator Roles',
                value=f'Members assigned a moderator roles are immune to the infraction system.\n{role_mentions}',
                inline=False,
            )
        else:
            embed.add_field(
                name='Moderator Roles',
                value='No moderator roles set. Members assigned a moderator roles are immune to the infraction system. Use the buttons below to add some.',
                inline=False,
            )

        enable_no_dms_open = settings.enable_no_dms_open
        embed.add_field(
            name='No DMs Open Enabled',
            value=(
                'Denotes if the bot should look for users with DMs open. If a user has DMs open, the bot will let the moderators know automatically.'
                if enable_no_dms_open
                else 'No DMs open setting is disabled. Enable it to monitor for members who have DMs open and get notified automatically.'
            ),
            inline=False,
        )

        status = 'Enabled' if settings.enable_infraction_counter else 'Disabled'
        embed.add_field(
            name='Infraction Counter',
            value=f'The infraction counter is a feature that keeps track of the number of infractions a user has. This feature is enabled by default.\n**Status**: {status}',
        )

        return embed

    async def _assign_notification_channel_after(
        self,
        interaction: discord.Interaction[FuryBot],
        channels: List[Union[app_commands.AppCommandChannel, app_commands.AppCommandThread]],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        channel = cast(discord.TextChannel, channels[0])
        await self.settings.edit(notification_channel_id=channel.id)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    # Top row: has notification channel, toggle no dms open, and toggle infraction counter

    @discord.ui.button(label='Assign Notification Channel', style=discord.ButtonStyle.primary)
    async def assign_notification_channel(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        ChannelSelect(
            after=self._assign_notification_channel_after,
            placeholder='Select a channel to assign as the notification channel for infractions.',
            parent=self,
            channel_types=[discord.ChannelType.text],
        )

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Toggle No DMs Open', style=discord.ButtonStyle.primary)
    async def toggle_no_dms_open(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        await self.settings.edit(enable_no_dms_open=not self.settings.enable_no_dms_open)
        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Toggle Infraction Counter', style=discord.ButtonStyle.primary)
    async def toggle_infraction_counter(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        await self.settings.edit(enable_infraction_counter=not self.settings.enable_infraction_counter)
        return await interaction.edit_original_response(embed=self.embed, view=self)

    # Second row: add/remove moderators

    async def _edit_moderator_after(
        self,
        action: ModeratorEditAction,
        interaction: discord.Interaction[FuryBot],
        users: List[Union[discord.Member, discord.User]],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        if action is ModeratorEditAction.ADD:
            new_moderator_ids = self.settings.moderator_ids.copy()
            new_moderator_ids.extend(user.id for user in users)
            await self.settings.edit(moderator_ids=new_moderator_ids)
        else:
            new_moderator_ids = self.settings.moderator_ids.copy()
            for user in users:
                new_moderator_ids.remove(user.id)

            await self.settings.edit(moderator_ids=new_moderator_ids)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Add Moderator', style=discord.ButtonStyle.green, row=1)
    async def add_moderator(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        UserSelect(
            after=functools.partial(self._edit_moderator_after, ModeratorEditAction.ADD),
            placeholder='Select users to add as moderators.',
            parent=self,
        )

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Moderator', style=discord.ButtonStyle.red, row=1)
    async def remove_moderator(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        UserSelect(
            after=functools.partial(self._edit_moderator_after, ModeratorEditAction.REMOVE),
            placeholder='Select users to remove as moderators.',
            parent=self,
        )

        return await interaction.edit_original_response(embed=self.embed, view=self)

    # Row 3: add/remove moderator roles
    async def _edit_moderator_roles_after(
        self,
        action: ModeratorEditAction,
        interaction: discord.Interaction[FuryBot],
        roles: List[discord.Role],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        if action is ModeratorEditAction.ADD:
            new_moderator_role_ids = self.settings.moderator_role_ids.copy()
            new_moderator_role_ids.extend(role.id for role in roles)
            await self.settings.edit(moderator_role_ids=new_moderator_role_ids)
        else:
            new_moderator_role_ids = self.settings.moderator_role_ids.copy()
            for role in roles:
                new_moderator_role_ids.remove(role.id)

            await self.settings.edit(moderator_role_ids=new_moderator_role_ids)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Add Moderator Role', style=discord.ButtonStyle.green, row=2)
    async def add_moderator_role(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        RoleSelect(
            after=functools.partial(self._edit_moderator_roles_after, ModeratorEditAction.ADD),
            placeholder='Select roles to add as moderator roles.',
            parent=self,
        )

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Moderator Role', style=discord.ButtonStyle.red, row=2)
    async def remove_moderator_role(
        self,
        interaction: discord.Interaction[FuryBot],
        button: discord.ui.Button[Self],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        RoleSelect(
            after=functools.partial(self._edit_moderator_roles_after, ModeratorEditAction.REMOVE),
            placeholder='Select roles to remove as moderator roles.',
            parent=self,
        )

        return await interaction.edit_original_response(embed=self.embed, view=self)
