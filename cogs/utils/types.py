from typing import TypedDict, List
from enum import Enum

class Reasons(Enum):
    activity = 1
    pfp = 2
    name = 3

class LockedOutInner(TypedDict):
    member_id: int
    bad_status: str
    raw_status: str
    extra: List[Reasons]
    
    
class LockedOut(TypedDict):
    member_id: LockedOutInner