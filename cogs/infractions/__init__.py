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

from typing import TYPE_CHECKING, Union

import discord
from discord import app_commands

from .counter import InfractionCounter
from .dm_notifications import DmNotifications
from .panel import DoesWantToCreateInfractionsSettings, InfractionsSettingsPanel
from .settings import InfractionsSettings as InfractionsSettings

if TYPE_CHECKING:
    from bot import FuryBot


class Infractions(DmNotifications, InfractionCounter):
    infractions = app_commands.Group(
        name='infractions',
        description='Manage infractions.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    @infractions.command(name='manage', description='Manage infraction settings.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def infractions_manage(self, interaction: discord.Interaction[FuryBot]) -> discord.InteractionMessage:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)

        settings = self.bot.get_infractions_settings(interaction.guild.id)
        if not settings:
            view = DoesWantToCreateInfractionsSettings(target=interaction)
            return await interaction.edit_original_response(view=view, embed=view.embed)

        panel = InfractionsSettingsPanel(settings=settings, target=interaction)
        return await interaction.edit_original_response(view=panel, embed=panel.embed)

    @infractions.command(name='count', description='Count the amount of infractions a member has.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member='The member to count infractions for.',
    )
    @app_commands.guild_only()
    async def infractions_count(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)

        settings = self.bot.get_infractions_settings(interaction.guild.id)
        if not settings:
            return await interaction.edit_original_response(
                content='No infractions settings found. Try `/infractions manage` to create them.'
            )

        if not settings.enable_infraction_counter:
            return await interaction.edit_original_response(
                content='Infraction counter is disabled. Enable it in the settings to use this command'
            )

        count = await settings.fetch_infractions_count_from(member.id)
        return await interaction.edit_original_response(content=f'{member.mention} has **{count} total infractions**.')

    @infractions.command(name='recent', description='Show the hyperlink to the most recent infraction.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member='The member to show the most recent infraction for.',
    )
    @app_commands.guild_only()
    async def infractions_recent(
        self, interaction: discord.Interaction[FuryBot], member: discord.Member
    ) -> discord.InteractionMessage:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)

        settings = self.bot.get_infractions_settings(interaction.guild.id)
        if not settings:
            return await interaction.edit_original_response(
                content='No infractions settings found. Try `/infractions manage` to create them.'
            )

        if not settings.enable_infraction_counter:
            return await interaction.edit_original_response(
                content='Infraction counter is disabled. Enable it in the settings to use this command'
            )

        infraction = await settings.fetch_most_recent_infraction_from(member.id)
        if not infraction:
            return await interaction.edit_original_response(content=f'{member.mention} has no infractions.')

        return await interaction.edit_original_response(
            content=f'{member.mention}\'s most recent infraction: [**Jump**]({infraction.url})'
        )

    @infractions.command(
        name='clear', description='Clear the infraction history for a target. This only deletes the database data.'
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    @app_commands.describe(
        target='The target to clear. A role clears the all members with the role. A member clears only the member.',
    )
    async def infractions_clear(
        self, interaction: discord.Interaction[FuryBot], target: Union[discord.Member, discord.Role]
    ) -> discord.InteractionMessage:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)

        settings = self.bot.get_infractions_settings(interaction.guild.id)
        if not settings:
            return await interaction.edit_original_response(
                content='No infractions settings found. Try `/infractions manage` to create them.'
            )

        if not settings.enable_infraction_counter:
            return await interaction.edit_original_response(
                content='Infraction counter is disabled. Enable it in the settings to use this command'
            )

        if isinstance(target, discord.Role):
            members = target.members
            for member in members:
                await settings.clear_infractions(member.id)

            return await interaction.edit_original_response(
                content=f'Cleared all infractions for **{len(members)}** members that have the {target.mention} role.'
            )

        await settings.clear_infractions(target.id)
        return await interaction.edit_original_response(content=f'Cleared all infractions for {target.mention}.')

    # Clears all the infraction history in the guild without a target
    @infractions.command(name='clear-all', description='Clear the infraction history for all members in the guild.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def infractions_clear_all(self, interaction: discord.Interaction[FuryBot]) -> discord.InteractionMessage:
        assert interaction.guild is not None
        await interaction.response.defer(ephemeral=True)

        settings = self.bot.get_infractions_settings(interaction.guild.id)
        if not settings:
            return await interaction.edit_original_response(
                content='No infractions settings found. Try `/infractions manage` to create them.'
            )

        if not settings.enable_infraction_counter:
            return await interaction.edit_original_response(
                content='Infraction counter is disabled. Enable it in the settings to use this command'
            )

        await settings.clear_all_infractions()
        return await interaction.edit_original_response(content='Cleared all infractions for all members in the guild.')


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(Infractions(bot))
