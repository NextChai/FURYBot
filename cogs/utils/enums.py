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

from typing import Type
from enum import Enum

__all__ = (
    'Reasons',
)


class Reasons(Enum):
    activity           = 1         # Member was locked out due to bad activity
    displayname        = 2         # Member was locked out due to bad name
    misc               = 3         # Member was locked for a reason not listed here
    avatar             = 4         # Member was locked for a bad avatar
    rules              = 5         # Member was locked for breaking rules.
    profanity          = 6         # Member has used terms that are profane.
    rolemention       = 7         # Member was locked for mentioning a role.
    massmention       = 8         # Member was locked for mentioning @here or @everyone
    
    @classmethod
    def type_to_string(cls, type: Reasons) -> str:
        """Converts a reason type to a human readable string.
        
        Parameters
        ----------
        type: :class:`Reasons`
            The type of reason to convert.
        
        Returns
        -------
        :class:`str`
            The formatted string.
        """
        mapping = {
            cls.activity: 'Activity',
            cls.displayname: 'DisplayName',
            cls.misc: 'Misc',
            cls.avatar: 'Avatar',
            cls.rules: 'Rules',
            cls.profanity: 'Profanity',
            cls.rolemention: 'RoleMention',
            cls.massmention: 'MassMention'
        }
        return mapping.get(type, 'Undefined')
    
    @classmethod
    def from_string(cls: Type[Reasons], string: str) -> Reasons:
        """Converts a human readable string to a reason type.
        
        Parameters
        ----------
        string: :class:`str`
            The string to convert.
            
        Returns
        -------
        :class:`Reasons`
            The converted type.
        
        Raises
        ------
        ValueError
            The string was not a valid reason type.
        """
        var = cls.__members__.get(string.lower()) 
        if var is None:
            raise ValueError(f'class Reasons does not have attribute {string}')
        
        return var