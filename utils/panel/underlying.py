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

from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Type, Union

import discord
from typing_extensions import Unpack

from ..ui import BaseModal, BaseView, BaseViewKwargs, ChannelSelect, RoleSelect, UserSelect
from . import ALL_PANELS
from .types import FieldType

if TYPE_CHECKING:
    from discord.ui.select import BaseSelect

    from bot import FuryBot

    from .field import Field
    from .panel import Panel


class _ModalConverter(BaseModal):
    def __init__(self, parent: UnderlyingPanelView, field: Field[Any], **kwargs: Any) -> None:
        super().__init__(**kwargs, bot=parent.bot)
        self.parent: UnderlyingPanelView = parent
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


class BooleanModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[bool]:
        if value.lower() in ('y', 'yes', 'true', 't', '1'):
            return True
        elif value.lower() in ('n', 'no', 'false', 'f', '0'):
            return False

        await interaction.followup.send(
            'You did not provide a valid boolean value. Example: `yes`, `no`, `true`, `false`', ephemeral=True
        )


class IntegerModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[int]:
        if value.isdigit():
            return int(value)

        await interaction.followup.send('You did not provide a valid integer value. Example: `10`', ephemeral=True)


class FloatModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[float]:
        try:
            return float(value)
        except ValueError:
            await interaction.followup.send('You did not provide a valid float value. Example: `10.1`', ephemeral=True)


class TextModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[str]:
        return value


class DatetimeModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[Any]:
        raise NotImplementedError


class TimeDeltaModal(_ModalConverter):
    async def transform(self, interaction: discord.Interaction[FuryBot], value: str) -> Optional[Any]:
        raise NotImplementedError


FIELD_MODAL_MAPPING: Mapping[FieldType, Type[_ModalConverter]] = {
    FieldType.BOOLEAN_MODAL: BooleanModal,
    FieldType.DATETIME_MODAL: DatetimeModal,
    FieldType.TIMEDELTA_MODAL: TimeDeltaModal,
    FieldType.INTEGER_MODAL: IntegerModal,
    FieldType.FLOAT_MODAL: FloatModal,
    FieldType.TEXT_MODAL: TextModal,
}


class ChannelSelectConverter(ChannelSelect['UnderlyingPanelView']):
    def __init__(self, parent: UnderlyingPanelView, field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        channels: List[Union[discord.app_commands.AppCommandChannel, discord.app_commands.AppCommandThread]],
    ) -> None:
        ...


class UserSelectConverter(UserSelect['UnderlyingPanelView']):
    def __init__(self, parent: UnderlyingPanelView, field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        users: List[Union[discord.Member, discord.User]],
    ) -> None:
        ...


class RoleSelectConverter(RoleSelect['UnderlyingPanelView']):
    def __init__(self, parent: UnderlyingPanelView, field: Field[Any]) -> None:
        super().__init__(after=self._callback, parent=parent)
        self.field: Field[Any] = field

    async def _callback(
        self,
        interaction: discord.Interaction[FuryBot],
        roles: List[discord.Role],
    ) -> None:
        ...


FIELD_SELECT_MAPPING: Mapping[FieldType, Type[BaseSelect[Any]]] = {
    FieldType.CHANNEL_SELECT: ChannelSelectConverter,
    FieldType.ROLE_SELECT: RoleSelectConverter,
    FieldType.USER_SELECT: UserSelectConverter,
}


class UnderlyingPanelButton(discord.ui.Button['UnderlyingPanelView']):
    def __init__(self, parent: UnderlyingPanelView, field: Field[Any]) -> None:
        label = field._button_kwargs.pop('label', f'Edit {field.name}')
        super().__init__(**field._button_kwargs, label=label)
        self.field: Field[Any] = field
        self.parent: UnderlyingPanelView = parent

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> Any:
        if any(self.field.type == field_type for field_type in FIELD_MODAL_MAPPING):
            # We have a modal
            modal = FIELD_MODAL_MAPPING[self.field.type](self.parent, self.field)
            return await interaction.response.send_modal(modal)

        await interaction.response.defer()

        if self.field.type == FieldType.SUBITEM:
            # We have a sub field, we need to try and find it in the registry.
            subpanel = ALL_PANELS.get(self.field.type.sub_item.__qualname__)
            if subpanel is None:
                raise ValueError(f'Panel {self.field.type.sub_item.__qualname__} is not registered as a panel.')

            # Awesome, we need to launch it's underlying view.
            view = self.parent.create_child(UnderlyingPanelView, subpanel)
            return await interaction.edit_original_response(view=view, embed=view.embed)
        elif self.field.type == FieldType.CHANNEL_SELECT:
            ...
        elif self.field.type == FieldType.ROLE_SELECT:
            ...
        elif self.field.type == FieldType.USER_SELECT:
            ...


class UnderlyingPanelView(BaseView):
    def __init__(self, panel: Panel[Any], **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.panel: Panel[Any] = panel

        for field in self.panel.fields.values():
            if field.ignored:
                continue

            self.add_item(UnderlyingPanelButton(self, field))

    @property
    def embed(self) -> discord.Embed:
        return discord.Embed(description='[test value]')
