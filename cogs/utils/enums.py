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
from enum import Enum

__all__ = (
    'Reasons',
)

class Reasons(Enum):
    activity      = 1         # Member was locked out due to bad activity
    displayname   = 2         # Member was locked out due to bad name
    misc          = 3         # Member was locked for a reason not listed here
    avatar        = 4         # Member was locked for a bad avatar
    rules         = 5         # Member was locked for breaking rules.
    profanity     = 6         # Member has used terms that are profane.
    
    @classmethod
    def type_to_string(cls, type: Reasons) -> str:
        mapping = {
            cls.activity: 'Activity',
            cls.displayname: "Name",
            cls.misc: 'Miscellaneous',
            cls.avatar: 'Avatar',
            cls.rules: 'Rules',
            cls.profanity: 'Profanity'
        }
        return mapping.get(type, 'Undefined')
    
    @classmethod
    def from_string(cls, string: str) -> Reasons:
        var = cls.__members__.get(string)
        if var is None:
            raise Exception(f'class Reasons does not have attribute {string}')
        return var