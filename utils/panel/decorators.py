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
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Mapping, Optional, Type, Union

import discord
from discord.utils import evaluate_annotation
from typing_extensions import dataclass_transform

from utils.query import QueryBuilder

from . import ALL_PANELS
from .field import Field, field
from .panel import Panel
from .types import MISSING, FieldType, T

if TYPE_CHECKING:
    from discord import Embed

    from bot import ConnectionType


CHANNEL_TYPE_MAPPING: Mapping[Type[Union[discord.abc.GuildChannel, discord.Thread]], Iterable[discord.ChannelType]] = {
    discord.TextChannel: (discord.ChannelType.text, discord.ChannelType.news),
    discord.VoiceChannel: (discord.ChannelType.voice,),
    discord.CategoryChannel: (discord.ChannelType.category,),
    discord.ForumChannel: (discord.ChannelType.forum,),
    discord.Thread: (discord.ChannelType.public_thread, discord.ChannelType.private_thread, discord.ChannelType.news_thread),
}

ANNOTWATION_FIELD_TYPE_MAPPING: Mapping[Type[Any], FieldType] = {
    discord.Role: FieldType.ROLE_SELECT,
    discord.User: FieldType.USER_SELECT,
    discord.Member: FieldType.USER_SELECT,
    datetime.datetime: FieldType.DATETIME_MODAL,
    datetime.timedelta: FieldType.TIMEDELTA_MODAL,
    str: FieldType.TEXT_MODAL,
    int: FieldType.INTEGER_MODAL,
    float: FieldType.FLOAT_MODAL,
    bool: FieldType.BOOLEAN_MODAL,
}


def infer_field_type(cls: Type[Any], annotation: str) -> FieldType:
    module = sys.modules[cls.__module__]
    builtins = module.__dict__['__builtins__']

    if isinstance(builtins, dict):
        module_globals: Dict[str, Any] = builtins['globals']()  # type: ignore
        module_locals: Dict[str, Any] = builtins['locals']()  # type: ignore
    elif isinstance(builtins, ModuleType):
        module_globals = builtins.globals()
        module_locals = builtins.locals()
    else:
        raise TypeError(f'Could not infer field type for {annotation!r}')

    try:
        evaluated = evaluate_annotation(annotation, module_globals, module_locals, {})  # type: ignore
    except NameError as exc:
        # Maybe this annotation is already a panel?
        raise TypeError(f'Could not infer field type for {annotation!r}') from exc

    if issubclass(evaluated, (discord.abc.GuildChannel, discord.Thread)):
        channel_types = CHANNEL_TYPE_MAPPING.get(evaluated, MISSING)
        return FieldType.CHANNEL_SELECT(channel_types=channel_types)
    elif evaluated is discord.Role:
        return FieldType.ROLE_SELECT
    elif issubclass(evaluated, discord.User):
        return FieldType.USER_SELECT
    elif evaluated is datetime.datetime:
        return FieldType.DATETIME_MODAL

    potential_type_mapping = ANNOTWATION_FIELD_TYPE_MAPPING.get(evaluated)
    if potential_type_mapping is not None:
        return potential_type_mapping

    # This may be a module-defined type, so let's see if we can shortcut it to a subitem.
    if hasattr(evaluated, '__panel__'):
        return FieldType.SUBITEM(evaluated)

    raise TypeError(f'Could not infer field type for {annotation!r}')


def create_fields(cls: Type[T], field_types: Mapping[str, FieldType]) -> Mapping[str, Field[T]]:
    annotations = cls.__annotations__
    fields: Dict[str, Field[T]] = {}
    for name, annotation in annotations.items():
        existing_field = cls.__dict__.get(name)
        default = MISSING  # Maybe a default we find in the existing field
        if existing_field is not None:
            # This could or could *not* be a field.
            if isinstance(existing_field, Field):
                if existing_field.annotation is not MISSING:
                    # This is a field that has an annotation
                    fields[existing_field.display_name] = existing_field
                    continue
                else:
                    # This is a field that does not have an annotation, so we can use the annotation we have here.
                    default = existing_field.default
            else:
                # This field does not have an annotation, so we can use the annotation we have here.
                default = existing_field

        # We can try and evaluate the annotation of the field type is not directly given
        field_type = field_types.get(name, MISSING)
        if field_type is MISSING:
            if existing_field is not None:
                if existing_field.type is not MISSING:
                    field_type = existing_field.type
                else:
                    if existing_field.ignored is False:
                        try:
                            field_type = infer_field_type(cls, annotation)
                        except TypeError as exc:
                            raise ValueError(f'Could not infer field type for {name!r} and type was not given.') from exc
            else:
                try:
                    field_type = infer_field_type(cls, annotation)
                except TypeError as exc:
                    raise ValueError(f'Could not infer field type for {name!r} and type was not given.') from exc

        fields[name] = Field(field_type, name=name, annotation=annotation, default=default)

    for field in field_types.keys():
        if field not in fields:
            raise ValueError(f'Field {field!r} was not found in the dataclass.')

    return fields


def create_init(cls: Type[T], fields: Mapping[str, Field[T]]) -> None:
    def _cls_init(self: T, **kwargs: Any) -> None:
        completed_fields: Dict[str, Any] = {}
        for name, value in kwargs.items():
            field = fields.get(name)
            if field is None:
                raise TypeError(f'__init__() got an unexpected keyword argument {name!r}')

            transformed = field.transform(value)
            completed_fields[name] = transformed

        # Transform all missing fields
        for name, field in fields.items():
            if name not in completed_fields:
                if field.default is MISSING:
                    # We're missing this field and there's no default, so we need to raise an error.
                    raise TypeError(f'__init__() missing required argument {name!r}')

                completed_fields[name] = field.transform(None)

        # Set all the fields
        for name, value in completed_fields.items():
            setattr(self, name, value)

    setattr(cls, '__init__', _cls_init)


def create_repr(cls: Type[T], fields: Mapping[str, Field[T]]) -> None:
    def _cls_repr(self: T) -> str:
        field_strings: List[str] = []
        for name in fields.keys():
            if name.startswith('_'):
                continue

            value = getattr(self, name)
            field_strings.append(f'{name}={value!r}')

        return f'<{cls.__name__} {" ".join(field_strings)}>'

    setattr(cls, '__repr__', _cls_repr)


def create_edit_function(panel: Panel[T], fields: Mapping[str, Field[T]]) -> None:
    id = fields.get('id', MISSING)
    if id is MISSING:
        raise ValueError('You must have an `id` field in your panel to use the `create_edit_func` option.')

    async def _edit_coro(self: Panel[T], connection: ConnectionType, **kwargs: Any) -> None:
        item_id = getattr(self, 'id')

        builder = QueryBuilder(table=self.table_name)
        builder.add_condition('id', item_id)

        for name, value in kwargs.items():
            builder.add_arg(name, value)
            setattr(self, name, value)

        await builder(connection)

    panel._edit_coroutine = _edit_coro


def split_camel_case(name: str) -> str:
    words: List[str] = []

    current = ''
    for element in name:
        if element.isupper():
            words.append(current)
            current = element
            continue

        current += element

    return ' '.join(words)


def register_panel(
    cls: Type[T],
    table_name: str,
    panel_name: Optional[str] = None,
    init: bool = True,
    repr: bool = True,
    create_edit_func: bool = True,
    create_embed: Optional[Callable[[Panel[T], T], Embed]] = None,
    **field_types: FieldType,
) -> Panel[T]:
    if ALL_PANELS.get(cls.__qualname__) is not None:
        raise ValueError(f'Panel {cls.__qualname__} is already registered as a panel.')

    # The panel name will be the given panel name or the class name (parsed to be split by camel case and titled)
    panel_name = panel_name or split_camel_case(cls.__name__)

    fields = create_fields(cls, field_types)
    panel = Panel(cls, table_name, panel_name, fields, create_embed=create_embed)

    if init:
        create_init(cls, fields)

    setattr(cls, '__slots__', tuple(fields.keys()))

    if repr:
        create_repr(cls, fields)

    if create_edit_func:
        create_edit_function(panel, fields)

    for field in fields.values():
        field.panel = panel

    ALL_PANELS[cls.__qualname__] = panel

    return panel


@dataclass_transform(field_specifiers=(field,))
def register(
    table_name: str,
    panel_name: Optional[str] = None,
    init: bool = True,
    repr: bool = True,
    create_edit_func: bool = True,
    create_embed: Optional[Callable[[Panel[T], T], Embed]] = None,
    **fields: FieldType,
) -> Callable[[Type[T]], Panel[T]]:
    def wrapped(cls: Type[T]) -> Panel[T]:
        return register_panel(
            cls,
            table_name,
            panel_name,
            init=init,
            repr=repr,
            create_embed=create_embed,
            create_edit_func=create_edit_func,
            **fields,
        )

    return wrapped
