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

from typing import TYPE_CHECKING, List, Union
from typing_extensions import Unpack, Self

import discord
from discord import app_commands

from utils import BaseView, BaseViewKwargs, ChannelSelect, RoleSelect, ConfirmationGetter

if TYPE_CHECKING:
    from bot import FuryBot
    from .settings import AttachmentRequestSettings


class AttachmentRequestSettingsPanel(BaseView):
    def __init__(self, settings: AttachmentRequestSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: AttachmentRequestSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Attachment Request Settings',
            description='Use the buttons below to change the settings for the attachment request system.',
        )

        channel = self.settings.channel
        if channel is None:
            embed.add_field(
                name='Notification Channel',
                value='The previous notification channel has been deleted. Please update the channel to one that exists.',
            )
        else:
            embed.add_field(name='Notification Channel', value=f'Channel: <#{channel.id}>')

        if self.settings.notification_role_id:
            role = self.settings.notification_role

            value = f'Role: {role and role.mention or "Deleted Role"}'

            if role is None:
                value += '\n**Warning**: This role has been deleted. Please update the role.'

            embed.add_field(name='Notification Role', value=value, inline=False)
        else:
            embed.add_field(name='Notification Role', value='No role set.', inline=False)

        return embed

    async def _change_channel_after(
        self,
        interaction: discord.Interaction[FuryBot],
        channels: List[Union[app_commands.AppCommandChannel, app_commands.AppCommandThread]],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()
        channel = channels[0]
        # We know from the select that this MUST be a text channel, so:
        if channel.type != discord.ChannelType.text:
            await interaction.followup.send('Invalid channel type. Please select a text channel.', ephemeral=True)
            return await interaction.edit_original_response(embed=self.embed, view=self)

        await self.settings.edit(channel_id=channel.id)
        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Change Channel', style=discord.ButtonStyle.green)
    async def change_channel(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        await interaction.response.defer()

        ChannelSelect(
            after=self._change_channel_after,
            parent=self,
            channel_types=[discord.ChannelType.text],
            placeholder='Select a channel...',
        )

        await interaction.edit_original_response(embed=self.embed, view=self)

    async def _change_notification_role_after(
        self, interaction: discord.Interaction[FuryBot], roles: List[discord.Role]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()
        role = roles[0]

        await self.settings.edit(notification_role_id=role.id)
        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Change Notification Role', style=discord.ButtonStyle.green)
    async def change_notification_role(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        await interaction.response.defer()

        RoleSelect(after=self._change_notification_role_after, parent=self, placeholder='Select a role...')

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Notification Role', style=discord.ButtonStyle.red, row=1)
    async def remove_notification_role(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        await interaction.response.defer()
        await self.settings.edit(notification_role_id=None)
        await interaction.edit_original_response(embed=self.embed, view=self)

    async def _delete_settings_confirmation_after(
        self, interaction: discord.Interaction[FuryBot], confirm: bool
    ) -> discord.InteractionMessage:
        await interaction.response.defer()
        if not confirm:
            return await interaction.edit_original_response(embed=self.embed, view=self)

        await self.settings.delete()
        return await interaction.edit_original_response(content='Attachment Request Settings have been deleted.', view=None)

    @discord.ui.button(label='Delete Attachment Request Settings', style=discord.ButtonStyle.red, row=1)
    async def delete_settings(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        ConfirmationGetter(
            after=self._delete_settings_confirmation_after,
            parent=self,
        )

        embed = self.bot.Embed(
            title='Delete Attachment Request Settings',
            description='Are you sure you want to delete the attachment request settings?',
        )
        return await interaction.edit_original_response(embed=embed, view=self)
