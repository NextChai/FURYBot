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
    
    @classmethod
    def type_to_string(cls, type: Reasons) -> str:
        mapping = {
            cls.activity: 'Activity',
            cls.displayname: "Name",
            cls.misc: 'Miscellaneous',
            cls.avatar: 'Avatar',
            cls.rules: 'Rules'
        }
        return mapping.get(type, 'Undefined')
    
    @classmethod
    def from_string(cls, string: str) -> Reasons:
        var = cls.__members__.get(string)
        if var is None:
            raise Exception(f'class Reasons does not have attribute {string}')
        return var