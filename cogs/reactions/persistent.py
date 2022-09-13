from __future__ import annotations

from typing import Any, Dict, List

import discord


class ReactionButton(discord.ui.Button['ReactionView']):
    def __init__(
        self,
        **options: Any,
    ) -> None:
        self.role_id: int = options['role_id']
        super().__init__(custom_id=options['custom_id'], label=options['label'], emoji=options['emoji'])

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message('Hey! Please try this again in 5 minutes, I\'m still rebooting!')

        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message('This role was deleted. Please let a moderator know!')

        if role in interaction.user.roles:
            meth = interaction.user.remove_roles
            added = False
        else:
            meth = interaction.user.add_roles
            added = True

        await meth(role, reason='Reaction roles.')
        return await interaction.response.send_message(
            f'{"Added" if added else "Removed"} {role.mention} {"from" if not added else "to"} you.', ephemeral=True
        )


class ReactionView(discord.ui.View):
    def __init__(self, button_reactions: List[Dict[str, Any]]) -> None:
        super().__init__(timeout=None)
        for item in button_reactions:
            self.add_item(ReactionButton(**item))
