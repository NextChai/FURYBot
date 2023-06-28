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

from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Generic, Mapping, Optional, Type, Union

from typing_extensions import Self

from . import get_panel
from .types import T, FieldType
from .underlying import UnderlyingPanelView
from .. import human_timestamp, human_timedelta

if TYPE_CHECKING:
    from discord import Embed, Interaction, Guild

    from bot import FuryBot

    from .field import Field


class Panel(Generic[T]):
    _edit_coroutine: Optional[Callable[..., Coroutine[Any, Any, None]]] = None

    def __init__(self, cls: Type[T], table_name: str, name: str, fields: Mapping[str, Field[T]], **kwargs: Any) -> None:
        self.cls: Type[T] = cls

        self.table_name: str = table_name
        self.name: str = name
        self.fields: Mapping[str, Field[T]] = fields

        self._create_embed_func: Optional[Callable[[Self, T], Embed]] = kwargs.get('create_embed', None)

    def __call__(self, *args: Any, **kwargs: Any) -> T:
        return self.cls(*args, **kwargs)

    def create_underlying_view(
        self, instance: T, target: Interaction[FuryBot], *, timeout: float = 120.0
    ) -> UnderlyingPanelView[T]:
        return UnderlyingPanelView(self, instance, timeout=timeout, parent=None, target=target)

    def create_embed(self, embed_cls: Callable[..., Embed], instance: T, guild: Guild) -> Embed:
        if self._create_embed_func is not None:
            return self._create_embed_func(self, instance)

        # An embed for a given panel can be shown in one of two ways. For each field in the panel,
        # it will have a corresponding embed field. If the field is a sub item, it will show a miniature
        # embed of the sub item.
        embed = embed_cls(title=f'Manage {self.name}', description='Use the buttons below to manage this panel.')

        for field_name, field in self.fields.items():
            if field.ignored:
                continue

            instance_field = getattr(instance, field_name)

            if field.type == FieldType.SUBITEM:
                # We can try and get the panel for this.
                panel = get_panel(field.type.sub_item.__qualname__)
                if panel is None:
                    raise ValueError(f'No panel found for {field.type.sub_item.__qualname__}')

                embed_field_data = panel.create_inline_embed(instance_field, guild)
                embed.add_field(**embed_field_data)
            elif field.type == FieldType.BOOLEAN_MODAL:
                embed.add_field(name=field.display_name, value=f'**Enabled**: {instance_field}')
            elif field.type == FieldType.DATETIME_MODAL:
                embed.add_field(name=field.display_name, value=human_timestamp(instance_field))
            elif field.type == FieldType.TIMEDELTA_MODAL:
                embed.add_field(name=field.display_name, value=human_timedelta(instance_field))
            elif field.type == FieldType.INTEGER_MODAL or field.type == FieldType.FLOAT_MODAL:
                embed.add_field(name=field.display_name, value=f'**Current Value**: {instance_field}')
            elif field.type == FieldType.CHANNEL_SELECT:
                channel = guild.get_channel_or_thread(instance_field)
                if channel is None:
                    embed.add_field(name=field.display_name, value='No Channel Found')
                else:
                    embed.add_field(name=field.display_name, value=channel.mention)
            elif field.type == FieldType.ROLE_SELECT:
                role = guild.get_role(instance_field)
                if role is None:
                    embed.add_field(name=field.display_name, value='No Role Found')
                else:
                    embed.add_field(name=field.display_name, value=role.mention)
            elif field.type == FieldType.USER_SELECT:
                client = guild._state._get_client()
                member_or_user = guild.get_member(instance_field) or client.get_user(instance_field)
                if member_or_user is None:
                    embed.add_field(name=field.display_name, value='No User Found')
                else:
                    embed.add_field(name=field.display_name, value=member_or_user.mention)
            elif field.type == FieldType.TEXT_MODAL:
                embed.add_field(name=field.display_name, value=f'**Current Value**: {instance_field}')

        return embed

    def create_inline_embed(self, instance: T, guild: Guild) -> Dict[str, Union[Any, bool]]:
        raise NotImplementedError
