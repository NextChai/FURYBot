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

import datetime
from typing import TYPE_CHECKING, Any, Generic, List, Mapping, Optional, Type, Union

import discord
from typing_extensions import Unpack

from ..ui import BaseModal, BaseView, BaseViewKwargs, ChannelSelect, RoleSelect, UserSelect
from ..time import TimeTransformer, ShortTime
from . import ALL_PANELS
from .types import T, FieldType

if TYPE_CHECKING:
    from bot import FuryBot

    from .field import Field
    from .panel import Panel


class _ModalConverter(BaseModal, Generic[T]):
    def __init__(self, parent: UnderlyingPanelView[T], field: Field[Any], **kwargs: Any) -> None:
        super().__init__(**kwargs, bot=parent.bot)
        self.parent: UnderlyingPanelView[T] = parent
        self.field: Field[Any] = field

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        await interaction.response.defer()

        child = self.children[0]
        assert isinstance(child, discord.ui.TextInput)

        transformed = await self.transform(interaction, child.value)
        if transformed is None:
            return

        edit_coro = self.field.panel._edit_coroutine
        if edit_coro is None:
            raise ValueError(f'Panel {self.field.panel} does not have an edit coroutine.')

        async with interaction.client.safe_connection() as connection:
            await edit_coro(connection=connection, **{self.field.name: transformed})

    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[Any]:
        raise NotImplementedError


class BooleanModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[bool]:
        if value.lower() in ('y', 'yes', 'true', 't', '1'):
            return True
        elif value.lower() in ('n', 'no', 'false', 'f', '0'):
            return False

        await interaction.followup.send(
            'You did not provide a valid boolean value. Example: `yes`, `no`, `true`, `false`', ephemeral=True
        )


class IntegerModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[int]:
        if value.isdigit():
            return int(value)

        await interaction.followup.send('You did not provide a valid integer value. Example: `10`', ephemeral=True)


class FloatModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[float]:
        try:
            return float(value)
        except ValueError:
            await interaction.followup.send('You did not provide a valid float value. Example: `10.1`', ephemeral=True)


class TextModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[str]:
        return value


class DatetimeModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[Any]:
        transformer = TimeTransformer(default='')
        return await transformer.transform(interaction, value)


class TimeDeltaModal(_ModalConverter[T]):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[Any]:
        short_time_re = ShortTime.compiled
        match = short_time_re.match(value)

        if not match:
            await interaction.followup.send(
                f'Invalid time format. Please try again.',
                ephemeral=True,
            )
            return None

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        data.pop('years', None)
        data.pop('months', None)

        return datetime.timedelta(**data)


FIELD_MODAL_MAPPING: Mapping[FieldType, Type[_ModalConverter[Any]]] = {
    FieldType.BOOLEAN_MODAL: BooleanModal[Any],
    FieldType.DATETIME_MODAL: DatetimeModal[Any],
    FieldType.TIMEDELTA_MODAL: TimeDeltaModal[Any],
    FieldType.INTEGER_MODAL: IntegerModal[Any],
    FieldType.FLOAT_MODAL: FloatModal[Any],
    FieldType.TEXT_MODAL: TextModal[Any],
}


class ChannelSelectConverter(ChannelSelect['UnderlyingPanelView[T]'], Generic[T]):
    def __init__(self, parent: UnderlyingPanelView[T], field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        channels: List[Union[discord.app_commands.AppCommandChannel, discord.app_commands.AppCommandThread]],
    ) -> None:
        ...


class UserSelectConverter(UserSelect['UnderlyingPanelView[T]'], Generic[T]):
    def __init__(self, parent: UnderlyingPanelView[T], field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        users: List[Union[discord.Member, discord.User]],
    ) -> None:
        ...


class RoleSelectConverter(RoleSelect['UnderlyingPanelView[T]'], Generic[T]):
    def __init__(self, parent: UnderlyingPanelView[T], field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        roles: List[discord.Role],
    ) -> None:
        ...


ConverterType = Type[Union[ChannelSelectConverter[T], RoleSelectConverter[T], UserSelectConverter[T]]]
FIELD_SELECT_MAPPING: Mapping[FieldType, ConverterType[Any]] = {
    FieldType.CHANNEL_SELECT: ChannelSelectConverter[Any],
    FieldType.ROLE_SELECT: RoleSelectConverter[Any],
    FieldType.USER_SELECT: UserSelectConverter[Any],
}


class UnderlyingPanelButton(discord.ui.Button['UnderlyingPanelView[T]'], Generic[T]):
    def __init__(self, parent: UnderlyingPanelView[T], field: Field[T]) -> None:
        super().__init__(label=field.display_name)
        self.field: Field[T] = field
        self.parent: UnderlyingPanelView[T] = parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> Any:
        if any(self.field.type == field_type for field_type in FIELD_MODAL_MAPPING):
            # We have a modal
            modal = FIELD_MODAL_MAPPING[self.field.type](self.parent, self.field)
            return await interaction.response.send_modal(modal)

        await interaction.response.defer()

        if any(self.field.type == field_type for field_type in FIELD_SELECT_MAPPING):
            select_cls = FIELD_SELECT_MAPPING[self.field.type]
            select_cls(parent=self.parent, field=self.field)
            return await interaction.edit_original_response(embed=self.parent.embed, view=self.parent)

        if self.field.type == FieldType.SUBITEM:
            # We have a sub field, we need to try and find it in the registry.
            subpanel = ALL_PANELS.get(self.field.type.sub_item.__qualname__)
            if subpanel is None:
                raise ValueError(f'Panel {self.field.type.sub_item.__qualname__} is not registered as a panel.')

            # Awesome, we need to launch it's underlying view.
            view = self.parent.create_child(UnderlyingPanelView[T], subpanel, self.parent.instance)
            return await interaction.edit_original_response(view=view, embed=view.embed)

        raise ValueError(f'Field type {self.field.type} is not supported.')


class UnderlyingPanelView(BaseView, Generic[T]):
    def __init__(self, panel: Panel[T], instance: T, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.panel: Panel[T] = panel
        self.instance: T = instance

        for field in self.panel.fields.values():
            if field.ignored:
                continue

            self.add_item(UnderlyingPanelButton(self, field))

    @property
    def embed(self) -> discord.Embed:
        if self.panel._create_embed_func is not None:
            return self.panel._create_embed_func(self.panel, self.instance)

        embed = discord.Embed(title=f'Manage {self.panel.name}', description='Use the buttons below to manage this panel.')

        for field in self.panel.fields.values():
            if field.ignored:
                continue

        return embed
