from __future__ import annotations

import asyncio
import binascii
import os
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypedDict,
    TypeVar,
    Union,
)

import discord
from discord.ext import commands
from typing_extensions import Self, Unpack

from utils.context import DummyContext
from utils.embed_maker import EmbedView
from utils.types.reaction_role import ReactionRoleCached, ReactionRoleReaction
from utils.view import BaseView, BaseViewKwargs

from .persistent import ReactionView

if TYPE_CHECKING:

    class _EmojiListDict(TypedDict):
        match_start: int
        match_end: int
        emoji: str

    emoji_list: Callable[[str], Any]
else:
    from emoji import emoji_list

ReactionT = TypeVar('ReactionT', bound='Union[Reaction, ButtonReaction]')


class Reaction:
    def __init__(self, role: discord.Role, emoji: discord.PartialEmoji) -> None:
        self.role: discord.Role = role
        self.emoji: discord.PartialEmoji = emoji
        self.custom_id: str = binascii.b2a_hex(os.urandom(15)).decode('utf-8')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'role_id': self.role.id,
            'guild_id': self.role.guild.id,
            'emoji': str(self.emoji),
            'custom_id': self.custom_id,
        }


class ButtonReaction:
    def __init__(self, role: discord.Role, emoji: Optional[discord.PartialEmoji], label: Optional[str] = None) -> None:
        self.role: discord.Role = role
        self.emoji: Optional[discord.PartialEmoji] = emoji
        self.label: Optional[str] = label
        self.custom_id: str = binascii.b2a_hex(os.urandom(15)).decode('utf-8')

    def to_dict(self) -> Dict[str, Any]:
        return {
            'role_id': self.role.id,
            'guild_id': self.role.guild.id,
            'emoji': str(self.emoji),
            'label': self.label,
            'custom_id': self.custom_id,
        }


class SelectChannelFinalizer(discord.ui.Select['BuildReactionRoleView']):
    def __init__(self, parent: BuildReactionRoleView, channels: List[discord.TextChannel]) -> None:
        self.parent: BuildReactionRoleView = parent
        self.channels: Mapping[int, discord.TextChannel] = {c.id: c for c in channels}

        super().__init__(
            placeholder='Select a channel...',
            options=[
                discord.SelectOption(
                    label=f'{channel.name} ({channel.category and channel.category.name or "No category."})',
                    value=str(channel.id),
                )
                for channel in channels
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        channel = self.channels[int(self.values[0])]

        if not channel.permissions_for(self.parent.guild.me):
            return await interaction.response.send_message('I can not send messages in that channel!', ephemeral=True)

        await interaction.response.defer()

        # Let's build our message, update the cache, send the message, then update to the DB
        embed = self.parent.r_embed
        assert embed

        kwargs: Dict[str, Union[discord.ui.View, discord.Embed]] = {'embed': embed}
        if self.parent.r_children:
            kwargs['view'] = ReactionView([i.to_dict() for i in self.parent.r_children])

        message = await channel.send(**kwargs)

        for reaction in self.parent.r_reactions:
            await message.add_reaction(reaction.emoji)

        async with self.parent.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                'INSERT INTO reaction_role.container(guild_id, channel_id, message_id, embed) '
                'VALUES ($1, $2, $3, $4) '
                'RETURNING id',
                self.parent.guild.id,
                message.channel.id,
                message.id,
                embed.to_dict(),
            )
            assert data

            reaction_role_id = data['id']

            if self.parent.r_children:
                await connection.executemany(
                    'INSERT INTO reaction_role.button (reaction_role, custom_id, message_id, guild_id, channel_id, role_id, label, emoji) '
                    'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
                    [
                        (
                            reaction_role_id,
                            child.custom_id,
                            message.id,
                            self.parent.guild.id,
                            message.channel.id,
                            child.role.id,
                            child.label,
                            str(child.emoji) if child.emoji else None,
                        )
                        for child in self.parent.r_children
                    ],
                )

            reaction_roles: Dict[str, ReactionRoleReaction] = {}
            if self.parent.r_reactions:
                for reaction in self.parent.r_reactions:
                    data = await connection.fetchrow(
                        'INSERT INTO reaction_role.reaction (reaction_role, message_id, guild_id, channel_id, role_id, emoji) '
                        'VALUES ($1, $2, $3, $4, $5, $6) '
                        'RETURNING *',
                        reaction_role_id,
                        message.id,
                        self.parent.guild.id,
                        message.channel.id,
                        reaction.role.id,
                        str(reaction.emoji),
                    )
                    assert data

                    reaction_roles[data['emoji']] = ReactionRoleReaction(
                        id=data['id'],
                        reaction_role=data['reaction_role'],
                        message_id=message.id,
                        guild_id=self.parent.guild.id,
                        channel_id=message.channel.id,
                        role_id=reaction.role.id,
                        emoji=str(reaction.emoji),
                    )

        packet = ReactionRoleCached(
            message_id=message.id,
            channel_id=message.channel.id,
            guild_id=self.parent.guild.id,
            reaction_roles=reaction_roles,
        )
        self.parent.bot.reaction_role_cache.setdefault(self.parent.guild.id, {})[message.id] = packet

        return await interaction.edit_original_response(
            view=None, embed=None, content=f'I\'ve posted your reaction role in {channel.mention}'
        )


class SelectRole(discord.ui.Select['AddReactionView']):
    def __init__(
        self, parent: AddReactionView, original_children: List[discord.ui.Item[Any]], roles: Sequence[discord.Role]
    ) -> None:
        self.parent: AddReactionView = parent
        self.original_children: List[discord.ui.Item[Any]] = original_children
        self.roles: Mapping[int, discord.Role] = {r.id: r for r in roles}

        super().__init__(
            placeholder='Select a role...',
            options=[
                discord.SelectOption(label=role.name, value=str(role.id), emoji=role.unicode_emoji)
                for role in self.roles.values()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        role = self.roles[int(self.values[0])]
        self.parent.role = role

        self.parent.clear_items()
        for child in self.original_children:
            self.parent.add_item(child)

        return await interaction.response.edit_message(view=self.parent, embed=self.parent.embed)


class SelectExistingReaction(discord.ui.Select['SelectExistingReactionView[ReactionT]']):
    def __init__(self, parent: SelectExistingReactionView[ReactionT], selectables: List[ReactionT]) -> None:
        self.parent: SelectExistingReactionView[ReactionT] = parent
        self.selectables: Mapping[str, ReactionT] = {r.custom_id: r for r in selectables}

        super().__init__(
            placeholder='Select an item...',
            options=[
                discord.SelectOption(
                    label=f'{index}. {item.role.name}',
                    emoji=item.emoji,
                    value=item.custom_id,
                    description=f'The {item.emoji} reaction role.',
                )
                for index, item in enumerate(self.selectables.values(), start=1)
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        self.parent.selected_reaction = self.selectables[self.values[0]]
        await interaction.response.edit_message(view=self.parent, embed=self.parent.embed)
        self.parent.stop()


class SelectExistingReactionView(BaseView, Generic[ReactionT]):
    def __init__(self, selectables: List[ReactionT], **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.add_item(SelectExistingReaction(self, selectables))
        self.selected_reaction: Optional[ReactionT] = None

    @property
    def embed(self) -> discord.Embed:
        return self.bot.Embed(
            title='Select an existing reaction...',
            description='Use the select below to select an existing reaction.',
        )


class SetLabelButtonModal(discord.ui.Modal):
    label: discord.ui.TextInput[Self] = discord.ui.TextInput(
        label='Enter a Label', max_length=32, placeholder='Enter a label here...'
    )

    def __init__(self, parent: AddReactionView) -> None:
        self.parent: AddReactionView = parent
        super().__init__(title='Add a Label')

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.parent.label = self.label.value
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class SetLabelButton(discord.ui.Button['AddReactionView']):
    def __init__(self, parent: AddReactionView) -> None:
        self.parent: AddReactionView = parent
        super().__init__(label='Set a Label')

    async def callback(self, interaction: discord.Interaction) -> Any:
        return await interaction.response.send_modal(SetLabelButtonModal(self.parent))


class AddReactionView(BaseView):
    def __init__(self, *, cls: Union[Type[Reaction], Type[ButtonReaction]], **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.cls: Union[Type[Reaction], Type[ButtonReaction]] = cls
        self.role: Optional[discord.Role] = None
        self.emoji: Optional[discord.PartialEmoji] = None
        self.label: Optional[str] = None  # max of 32 chars

        super().__init__(**kwargs)

        if self.cls is ButtonReaction:
            self.remove_item(self.finalize)
            self.add_item(SetLabelButton(self))
            self.add_item(self.finalize)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(title='Add a Reaction', description='Use the buttons below to add your reaction.')
        embed.add_field(name='Role', value=self.role.mention if self.role else "No role added.")
        embed.add_field(name='Emoji', value=str(self.emoji) if self.emoji else "No emoji added.")

        if self.cls is ButtonReaction:
            embed.add_field(name='Label', value=self.label or "No label added.")

        return embed

    @discord.ui.button(label='Set Role')
    async def set_role(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        original_children = self.children
        select = SelectRole(self, original_children, self.guild.roles)

        self.clear_items()
        self.add_item(select)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Set Emoji')
    async def set_emoji(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        await interaction.response.edit_message(
            content='Type the emoji you want to use. I\'ll be waiting for your message. '
            'Pro tip: Don\'t have nitro? No worries! Type the name of the emoji and I\'ll take care of the rest.',
            view=None,
            embed=None,
        )

        try:
            message: discord.Message = await self.bot.wait_for(
                'message', check=lambda m: m.author == self.author and m.channel == interaction.channel, timeout=300
            )
        except asyncio.TimeoutError:
            return self.stop()

        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        match = re.match(
            r'<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>',
            message.content,
        )

        if not match:
            # Let's try an emoji converter, and backup to unicode if all else fails
            if message.content.startswith(':') and message.content.endswith(':'):
                # Non-nitro user has failed to mention a nitro only emote
                message.content = message.content[1:-1]

            try:
                full = await commands.EmojiConverter().convert(DummyContext(interaction), message.content)  # pyright: ignore
                emoji = discord.PartialEmoji.from_str(str(full))
            except Exception:
                # We can try and fall back to unicode emojis
                emojis: List[_EmojiListDict] = emoji_list(message.content)
                if not emojis:
                    return await interaction.edit_original_response(content='No Emoji Given!', view=self)

                emoji = discord.PartialEmoji.from_str(emojis[0]['emoji'])
        else:
            animated, name, id = match.groups()
            emoji = discord.PartialEmoji.from_str(f'{f"{animated}:" if animated else ""}{name}:{id}')

        # Check to see if we already have this emoji anywhere
        assert isinstance(self.parent, BuildReactionRoleView)
        if self.cls is Reaction:
            if discord.utils.find(lambda r: r.emoji == emoji, self.parent.r_reactions):
                return await interaction.edit_original_response(embeds=self.parent._embeds, view=self.parent)

        self.emoji = emoji
        return await interaction.edit_original_response(embed=self.embed, view=self, content=None)

    @discord.ui.button(label='Add Item')
    async def finalize(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.role:
            return await interaction.response.send_message('You need to add a role first.', ephemeral=True)

        if self.cls is Reaction:
            if not self.emoji:
                return await interaction.response.send_message('You need to add an emoii first.', ephemeral=True)
        else:
            if not self.emoji and not self.label:
                return await interaction.response.send_message('You must have an emoji or a label first.', ephemeral=True)

        assert isinstance(self.parent, BuildReactionRoleView)
        if self.cls is ButtonReaction:
            reaction = ButtonReaction(self.role, self.emoji, self.label)
            button.custom_id = reaction.custom_id
            self.parent.r_children.append(reaction)
        else:
            assert self.emoji
            self.parent.r_reactions.append(Reaction(self.role, self.emoji))

        return await interaction.response.edit_message(view=self.parent, embeds=self.parent._embeds)


class BuildReactionRoleView(BaseView):
    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)

        self.r_children: List[ButtonReaction] = []
        self.r_embed: Optional[discord.Embed] = None
        self.r_reactions: List[Reaction] = []

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Create Reaction Role', description='Use the buttons below to create and manage your reaction role.'
        )
        embed.add_field(
            name='Create your Embed',
            value='Use the "Create Embed" button below to create the embed for your reaction role message. '
            'Please note the bot will not make an effort to do this for you, it\'s up to you to style your '
            'own embed.',
            inline=False,
        )

        embed.add_field(
            name='Reactions',
            value='\n'.join(
                [f'{reaction.emoji}: {reaction.role.mention}' for reaction in self.r_reactions] or ['No reactions.']
            ),
        )

        embed.add_field(
            name='Buttons',
            value='\n'.join(
                [f'{button.label} ({button.emoji}): {button.role.mention}' for button in self.r_children] or ['No buttons.']
            ),
        )
        return embed

    @property
    def _embeds(self) -> List[discord.Embed]:
        return [e for e in (self.embed, self.r_embed) if e]

    @discord.ui.button(label='Add Reaction')
    async def add_reaction(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if len(self.r_children) == 20:
            return await interaction.response.send_message('You can only have 20 reactions.', ephemeral=True)

        view = AddReactionView(cls=Reaction, **self.dump_kwargs())
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Remove Reaction')
    async def remove_reaction(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.r_reactions:
            return await interaction.response.send_message('There are no reactions to remove.', ephemeral=True)

        view = SelectExistingReactionView(self.r_reactions, **self.dump_kwargs())
        await interaction.response.edit_message(view=view, embed=view.embed)
        await view.wait()

        selected = view.selected_reaction
        if not selected:
            return

        self.r_reactions.remove(selected)
        await interaction.edit_original_response(embeds=self._embeds, view=self)

    @discord.ui.button(label='Add Button')
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if len(self.r_children) == 20:
            return await interaction.response.send_message('You can only have 20 buttons.', ephemeral=True)

        view = AddReactionView(cls=ButtonReaction, **self.dump_kwargs())
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Remove Button')
    async def remove_button(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.r_children:
            return await interaction.response.send_message('There are no buttons to remove.', ephemeral=True)

        view = SelectExistingReactionView(self.r_children, **self.dump_kwargs())
        await interaction.response.edit_message(view=view, embed=view.embed)
        await view.wait()

        selected = view.selected_reaction
        if not selected:
            return

        self.r_children.remove(selected)
        await interaction.edit_original_response(embeds=self._embeds, view=self)

    @discord.ui.button(label='Create Embed')
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        view = EmbedView(target=interaction)
        await interaction.response.edit_message(embed=view.embed, view=view)

        await asyncio.wait((view.wait(), view.embed_ready), return_when=asyncio.FIRST_COMPLETED)

        if not view.embed_ready.done():
            # The user did not finish the embed,
            # and the view has timed out.
            return

        embed_done: discord.Interaction = view.embed_ready.result()
        self.r_embed = view.edited_embed
        await embed_done.response.edit_message(view=self, embeds=self._embeds)

    @discord.ui.button(label='Finalize')
    async def finalize(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.r_embed:
            return await interaction.response.send_message('You must create an embed before finalizing.', ephemeral=True)

        if not self.r_children and not self.r_reactions:
            return await interaction.response.send_message(
                'This reaction role has no buttons or reations. Add at least on to finalize.', ephemeral=True
            )

        self.clear_items()

        assert interaction.guild

        for chunk in discord.utils.as_chunks(interaction.guild.text_channels, max_size=20):
            item = SelectChannelFinalizer(self, chunk)
            self.add_item(item)

        return await interaction.response.edit_message(view=self)
