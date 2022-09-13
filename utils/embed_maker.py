from __future__ import annotations

import asyncio
from typing import Any, List, Literal, Mapping, Optional

import discord
from typing_extensions import Self, Unpack

from utils.modal import BaseModal

from .view import BaseView, BaseViewKwargs


class EmbedAuthorChanger(BaseModal):
    name: discord.ui.TextInput[Self] = discord.ui.TextInput(label='Name', max_length=256, required=False)
    url: discord.ui.TextInput[Self] = discord.ui.TextInput(label='URL', required=False)
    icon_url: discord.ui.TextInput[Self] = discord.ui.TextInput(label='Icon URL', required=False)

    def __init__(
        self,
        edited_embed: discord.Embed,
        parent: EmbedView,
    ) -> None:
        self.edited_embed: discord.Embed = edited_embed
        self.parent: EmbedView = parent
        super().__init__(title='Edit Embed Author', bot=self.parent.bot)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.edited_embed.set_author(name=self.name.value, url=self.url.value, icon_url=self.icon_url.value)
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class EmbedFooterChanger(BaseModal):
    text: discord.ui.TextInput[Self] = discord.ui.TextInput(label='Text', required=False)
    icon_url: discord.ui.TextInput[Self] = discord.ui.TextInput(label='Icon URL', required=False)

    def __init__(
        self,
        edited_embed: discord.Embed,
        parent: EmbedView,
    ) -> None:
        self.edited_embed: discord.Embed = edited_embed
        self.parent: EmbedView = parent
        super().__init__(title='Edit Embed Footer', bot=self.parent.bot)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.edited_embed.set_footer(text=self.text.value, icon_url=self.icon_url.value)
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class EmbedImageChanger(BaseModal):
    def __init__(
        self,
        edited_embed: discord.Embed,
        parent: EmbedView,
        *,
        method: Literal['set_image', 'set_thumbnail'] = 'set_image',
        title: Optional[str] = None,
    ) -> None:
        self.method: str = method
        self.edited_embed: discord.Embed = edited_embed
        self.parent: EmbedView = parent
        super().__init__(title=title or 'Change Image', bot=self.parent.bot)

        self.item: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label='Image URL', placeholder='Change image url...', required=False
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        getattr(self.edited_embed, self.method)(url=self.item.value)
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class EmbedAttributeChanger(BaseModal):
    def __init__(
        self,
        target: Any,
        parent: BaseView,
        attribute: str,
        *,
        title: Optional[str] = None,
        style: discord.TextStyle = discord.TextStyle.short,
        max_length: int = 100,
    ) -> None:
        self.target: Any = target
        self.parent: BaseView = parent
        self.attribute: str = attribute
        super().__init__(title=f'Change Embed {self.attribute.title()}', bot=self.parent.bot)

        self.item: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label=title or f'Change {attribute.title()}',
            placeholder=f'Enter the new {attribute}...',
            required=False,
            style=style,
            max_length=max_length,
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        setattr(self.target, self.attribute, self.item.value)
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class EmbedFieldChanger(BaseModal):
    def __init__(
        self,
        parent: BaseView,
        field_index: int,
        edited_embed: discord.Embed,
        attribute: Literal['name', 'value', 'inline'],
        *,
        style: discord.TextStyle = discord.TextStyle.short,
        max_length: int = 100,
    ) -> None:
        self.parent: BaseView = parent
        self.field_index: int = field_index
        self.edited_embed: discord.Embed = edited_embed
        self.attribute: Literal['name', 'value', 'inline'] = attribute

        super().__init__(bot=self.parent.bot, title=f'Change {attribute.title()}')
        self.item: discord.ui.TextInput[Self] = discord.ui.TextInput(
            label=f'Change {attribute.title()}', style=style, max_length=max_length, placeholder=f'Change {attribute}...'
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.edited_embed._fields[self.field_index][self.attribute] = self.item.value
        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


class RemoveSelectField(discord.ui.Select[BaseView]):
    def __init__(
        self,
        before_children: List[discord.ui.Item[Any]],
        parent: BaseView,
        edited_embed: discord.Embed,
    ) -> None:
        self.base_children: List[discord.ui.Item[Any]] = before_children
        self.parent: BaseView = parent
        self.edited_embed: discord.Embed = edited_embed
        self.selected_field_index: Optional[int] = None

        super().__init__(
            placeholder='Select a field...',
            options=[
                discord.SelectOption(
                    label=field.name,  # pyright: ignore
                    value=str(index),
                    description=field.value and field.value[:100],
                )
                for index, field in enumerate(edited_embed.fields)
            ],
        )

    async def after(self, interaction: discord.Interaction) -> Any:
        pass

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = int(self.values[0])
        self.selected_field_index = selected

        self.edited_embed.remove_field(self.selected_field_index)
        self.parent.clear_items()
        for child in self.base_children:
            self.parent.add_item(child)

        return await interaction.response.edit_message(embed=self.parent.embed, view=self.parent)


# Edit field value
class AddFieldView(BaseView):
    def __init__(self, edited_embed: discord.Embed, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.edited_embed: discord.Embed = edited_embed
        self.name: Optional[str] = None
        self.value: Optional[str] = None
        self.inline: bool = True
        super().__init__(**kwargs)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'Create a Field',
            description='Use the buttons below to create your field. Each field MUST have a name and value.',
        )

        embed.add_field(name='Name', value=str(self.name))
        embed.add_field(name='Value', value=str(self.value))
        embed.add_field(name='Inline', value=self.inline)
        return embed

    @discord.ui.button(label='Set Name')
    async def set_name(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        # We can strap onto EmbedAttributeChanger here
        modal = EmbedAttributeChanger(self, self, 'name', title='Change Field Name')
        return await interaction.response.send_modal(modal)

    @discord.ui.button(label='Set Value')
    async def set_value(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        # We can strap onto EmbedAttributeChanger here
        modal = EmbedAttributeChanger(
            self, self, 'value', title='Change Field Value', style=discord.TextStyle.long, max_length=1200
        )
        return await interaction.response.send_modal(modal)

    # NOTE: move later for a state
    @discord.ui.button(label='Toggle Inline')
    async def toggle_inline(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        self.inline = not self.inline
        return await interaction.response.edit_message(view=self, embed=self.embed)

    @discord.ui.button(label='Add Field')
    async def finalize(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.name or not self.value:
            return await interaction.response.send_message('You must have a name and value to add a field.', ephemeral=True)

        self.edited_embed.add_field(name=self.name, value=self.value, inline=self.inline)

        assert self.parent and self.parent.parent
        return await interaction.response.edit_message(embed=self.parent.parent.embed, view=self.parent.parent)


# A view that represents a field, allows
# to edit the name and value of the field
class FieldView(BaseView):
    def __init__(self, index: int, edited_embed: discord.Embed, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.edited_embed: discord.Embed = edited_embed
        self.index: int = index
        super().__init__(**kwargs)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(title=f'Field at Index {self.index}', description='Use the buttons below to edit your field')

        field = self.edited_embed.fields[self.index]
        embed.add_field(name='Name', value=str(field.name))
        embed.add_field(name='Value', value=str(field.value))
        embed.add_field(name='Inline', value=str(field.inline))
        return embed

    # Add edit field name, value, and inline buttons
    # Add field delete
    @discord.ui.button(label='Edit Name')
    async def edit_name(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        # We can strap onto EmbedAttributeChanger here
        modal = EmbedFieldChanger(parent=self, field_index=self.index, edited_embed=self.edited_embed, attribute='name')
        return await interaction.response.send_modal(modal)

    @discord.ui.button(label='Edit Value')
    async def edit_value(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        # We can strap onto EmbedAttributeChanger here
        modal = EmbedFieldChanger(parent=self, field_index=self.index, edited_embed=self.edited_embed, attribute='value')
        return await interaction.response.send_modal(modal)

    # NOTE: Make button class later for state
    @discord.ui.button(label='Toggle Inline')
    async def toggle_inline(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        self.edited_embed.fields[self.index].inline = not self.edited_embed.fields[self.index].inline
        return await interaction.response.edit_message(view=self, embed=self.embed)


# Allows the user to select a field to edit
# launches the FieldView
class FieldSelect(discord.ui.Select['FieldsView']):
    def __init__(self, parent: FieldsView) -> None:
        self.edited_embed: discord.Embed = parent.edited_embed
        self.parent: FieldsView = parent
        self.field_mapping: Mapping[int, Any] = dict(enumerate(self.edited_embed.fields))
        super().__init__(
            placeholder='Select field to edit...',
            options=[
                discord.SelectOption(label=field.name[:100], value=str(index), description=field.value[:100])
                for index, field in self.field_mapping.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> Any:
        field_index = int(self.values[0])
        view = FieldView(field_index, self.edited_embed, **self.parent.dump_kwargs())
        return await interaction.response.edit_message(embed=view.embed, view=view)


# Remove field
# Clear fields
class FieldsView(BaseView):
    def __init__(self, edited_embed: discord.Embed, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.edited_embed: discord.Embed = edited_embed

        if edited_embed.fields:
            self.add_item(FieldSelect(self))

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Embed Fields',
            description='Use the buttons below to add new fields, remove existing fields, and clear all fields. '
            '   The fields below represent how your Embed\'s fields are going to look.',
        )

        for field in self.edited_embed.fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

        return embed

    @discord.ui.button(label='Add Field')
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        view = AddFieldView(self.edited_embed, **self.dump_kwargs())
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Remove Field')
    async def remove_field(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        if not self.edited_embed.fields:
            return await interaction.response.send_message('There are no fields to remove.', ephemeral=True)

        children = self.children
        select = RemoveSelectField(children, self, self.edited_embed)
        self.clear_items()
        self.add_item(select)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Clear Fields')
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        self.edited_embed.clear_fields()
        return await interaction.response.edit_message(view=self, embed=self.embed)


class EmbedView(BaseView):
    def __init__(self, edited_embed: Optional[discord.Embed] = None, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.edited_embed: discord.Embed = edited_embed or discord.Embed()
        self.embed_ready: asyncio.Future[discord.Interaction] = self.bot.loop.create_future()

    @property
    def embed(self) -> discord.Embed:
        if len(self.edited_embed) == 0:
            # We don't have anything, but images dont display correctly
            if any(
                (
                    self.edited_embed.thumbnail,
                    self.edited_embed.image,
                    self.edited_embed.author.icon_url,
                    self.edited_embed.footer.icon_url,
                )
            ):
                return self.edited_embed

        return (
            self.edited_embed
            if len(self.edited_embed) > 0
            else self.bot.Embed(
                title='Use the buttons below to edit your embed.',
                description='Your embed has nothing! Use the buttons below to create it!',
            )
        )

    @discord.ui.button(label='Set Author')
    async def author_button(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        return await interaction.response.send_modal(EmbedAuthorChanger(self.edited_embed, self))

    @discord.ui.button(label='Change Title')
    async def title(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        modal = EmbedAttributeChanger(self.edited_embed, self, 'title')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Description')
    async def description(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        modal = EmbedAttributeChanger(self.edited_embed, self, 'description', style=discord.TextStyle.long, max_length=2000)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Fields')
    async def fields(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        view = FieldsView(self.edited_embed, **self.dump_kwargs())
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Set Footer')
    async def footer(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        return await interaction.response.send_modal(EmbedFooterChanger(self.edited_embed, parent=self))

    @discord.ui.button(label='Set Thumbnail')
    async def set_thumbnail(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        modal = EmbedImageChanger(self.edited_embed, self, method='set_thumbnail', title='Change Thumbnail')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Set Image')
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        await interaction.response.send_modal(EmbedImageChanger(self.edited_embed, self))

    @discord.ui.button(label='Finalize')
    async def finalize(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:

        self.embed_ready.set_result(interaction)
