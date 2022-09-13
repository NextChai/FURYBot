from __future__ import annotations

from typing import TYPE_CHECKING, List, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.bases.cog import BaseCog
from utils.errors import AutocompleteValidationException
from utils.types.reaction_role import ReactionRoleCached

from .operations import BuildReactionRoleView

if TYPE_CHECKING:
    from bot import FuryBot


class ReactionRoleTransformer(app_commands.Transformer):
    """Represents a reaction role transformer. Will allow the user
    to select any given existing reaction role and perform an operation on it.
    Such as edit or deleting it.
    """

    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str]
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        """|coro|

        Will perform an autocomplete interaction response giving the user the available
        reaction roles they can select from.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by the user typing something.
        value: Any
            The value the user typed.

        Returns
        -------
        List[:class:`app_commands.Choice`]
            A list of choices the user can select from.
        """
        assert interaction.guild is not None

        bot: FuryBot = interaction.client  # type: ignore
        existing = bot.reaction_role_cache.get(interaction.guild.id)
        if not existing:
            return []

        choices: List[app_commands.Choice[Union[int, float, str]]] = []
        for message_id, item in existing.items():
            channel = interaction.guild.get_channel(item['channel_id'])
            choices.append(
                app_commands.Choice(
                    name=f'#{channel.name} (Message ID: {message_id})'
                    if channel
                    else f'{item["channel_id"]} Deleted (Message ID: {message_id})',
                    value=str(message_id),
                )
            )

        return choices

    async def transform(self, interaction: discord.Interaction, value: str) -> ReactionRoleCached:
        """|coro|

        Transforms the given user input to a :class:`ReactionRoleCached`.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created by the user invoking the slash comand.
        value: Any
            The value the user typed.

        Returns
        -------
        :class:`ReactionRoleCached`
            An instance of :class:`ReactionRoleCached` the user selected from the available choices.

        Raises
        ------
        AutocompleteValidationException
            The user did not enter a valid reaction role item
            from the choices they were given.
        """
        assert interaction.guild is not None

        bot: FuryBot = interaction.client  # type: ignore
        existing = bot.reaction_role_cache.get(interaction.guild.id)
        if not existing:
            raise AutocompleteValidationException(interaction, 'No reaction roles to delete.')

        if not value.isdigit():
            raise AutocompleteValidationException(interaction, 'Incorrect reaction role to delete.')

        reaction_role = existing.get(int(value))
        if not reaction_role:
            raise AutocompleteValidationException(interaction, 'Reaction role not found.')

        return reaction_role


class ReactionRoles(BaseCog):
    """Commands to manage and create reaction roles."""

    reaction = app_commands.Group(
        name='reaction', description='Manage reaction roles', extras={'custom_id': '7a3683330a68749163e01d374088cf'}
    )
    reaction_role = app_commands.Group(
        name='role',
        description='Manage reaction roles',
        parent=reaction,
        extras={'custom_id': '81a0ecd3fa0aa1344122f0932e249a'},
    )

    @reaction_role.command(
        name='create',
        description='Create a reaction role with buttons and roles.',
        extras={'custom_id': 'b9e1906ae4a0db16c3bb3dc399efdf'},
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def reaction_role_create(self, interaction: discord.Interaction) -> None:
        """Create a reaction role. When called, will launch a view assisting the user
        in creating a reaction role system.
        """
        assert interaction.guild is not None

        existing = self.bot.reaction_role_cache.get(interaction.guild.id)
        if existing and len(existing) == 5:
            return await interaction.response.send_message(
                'You can\'t have more than 5 reaction roles at a time.', ephemeral=True
            )

        view = BuildReactionRoleView(target=interaction)
        return await interaction.response.send_message(embed=view.embed, view=view)

    @reaction_role.command(
        name='delete',
        description='Delete an existing reaction role.',
        extras={'custom_id': '106bb963c74c721b085182b3f769b2'},
    )
    @app_commands.describe(reaction='The reaction role you want to delete.')
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def reaction_role_delete(
        self, interaction: discord.Interaction, reaction: app_commands.Transform[ReactionRoleCached, ReactionRoleTransformer]
    ) -> None:
        """Delete an existing reaction role.

        Parameters
        ----------
        reaction: Message
            The existing reaction role you want to delete.
        """
        assert interaction.guild is not None
        assert isinstance(interaction.channel, discord.TextChannel)

        message = interaction.channel.get_partial_message(reaction['message_id'])
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        await self.bot.pool.execute('DELETE FROM reaction_role.container WHERE message_id = $1', reaction['message_id'])
        return await interaction.response.send_message('Deleted.', ephemeral=True)

    @commands.Cog.listener('on_raw_reaction_add')
    @commands.Cog.listener('on_raw_reaction_remove')
    async def reaction_event_listener(self, payload: discord.RawReactionActionEvent) -> None:
        """|coro|

        A multiple event handler dedicated to handling the procesing of adding
        and removing roles based upon reaction role reactions.

        Parameters
        ----------
        payload: :class:`RawReactionActionEvent`
            The raw payload given to the client from a reaction
            being pressed.
        """
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            # Received an event for an unknown guild
            return

        packet = self.bot.reaction_role_cache.get(payload.guild_id)
        if not packet:
            return

        data = packet.get(payload.message_id)
        if not data:
            return

        reaction_roles = data['reaction_roles']
        if not reaction_roles:
            return

        reaction_role = reaction_roles.get(str(payload.emoji))
        if not reaction_role:
            return

        role = guild.get_role(reaction_role['role_id'])
        if not role:
            return

        member = payload.member or guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        meth = member.add_roles if payload.event_type == 'REACTION_ADD' else member.remove_roles
        await meth(role, reason='Reaction roles')


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(ReactionRoles(bot))
