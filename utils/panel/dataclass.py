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

from types import NoneType

from typing import Any, Callable, Dict, Optional, Type, List, Union
from typing_extensions import dataclass_transform

from .types import MISSING, T


class DataclassField:
    def __init__(
        self,
        name: str = MISSING,
        annotation: Any = MISSING,
        default: Any = MISSING,
        converter: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        self.name: str = name
        self.annotation: Any = annotation
        self.default: Any = default
        self.converter: Optional[Callable[[Any], Any]] = converter

    def __repr__(self) -> str:
        return f'<DataclassField name={self.name!r} annotation={self.annotation!r} default={self.default!r} converter={self.converter!r}>'

    def transform(self, value: Optional[Any]) -> Any:
        if value is None:
            # We can't do anything if the default *is* missing, so value
            # will have to stay as None
            if self.default is not MISSING:
                value = self.default

        if self.converter is not None:
            value = self.converter(value)

        return value


def field(
    *,
    name: Optional[str] = None,
    annotation: Any = MISSING,
    default: Any = MISSING,
    converter: Optional[Callable[[Any], Any]] = None,
) -> Any:
    # The field class doesn't take the same types of arguments as the decorator,
    # so we need to do some work to make sure we can handle both.
    data: Dict[str, Any] = {'default': default, 'converter': converter}

    if name is not None:
        data['name'] = name

    if annotation is not MISSING:
        data['annotation'] = annotation

        if default is MISSING:
            # We can check if the annotation is Optional. If it is the default
            # here can be None.
            origin = getattr(annotation, '__origin__', None)
            if origin is not None and origin is Union:
                args = origin.__args__
                if args.index(NoneType) == len(args) - 1:
                    data['default'] = None

    return DataclassField(**data)


@dataclass_transform(field_specifiers=(field,))
def create_dataclass(cls: Type[T], *, init: bool = True, repr: bool = True, slots: bool = True) -> Type[T]:
    # Let's go through and create all our fields first.
    annotations = cls.__annotations__
    fields: Dict[str, DataclassField] = {}
    for name, annotation in annotations.items():
        existing_field = cls.__dict__.get(name)
        default = MISSING  # Maybe a default we find in the existing field
        if existing_field is not None:
            # This could or could *not* be a field.
            if isinstance(existing_field, DataclassField):
                fields[name] = existing_field
                continue

            # This has a default but is not a field, let's create a new one and set this as the default.
            default = existing_field
            continue

        fields[name] = DataclassField(name=name, annotation=annotation, default=default)

    setattr(cls, '__dataclass_fields__', fields)

    # Need to create our init now
    if init:

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

    if slots:
        setattr(cls, '__slots__', tuple(fields.keys()))

    # Need to create our repr now
    if repr:

        def _cls_repr(self: T) -> str:
            field_strings: List[str] = []
            for name in fields.keys():
                if name.startswith('_'):
                    continue

                value = getattr(self, name)
                field_strings.append(f'{name}={value!r}')

            return f'<{cls.__name__} {" ".join(field_strings)}>'

        setattr(cls, '__repr__', _cls_repr)

    return cls
