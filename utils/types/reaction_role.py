from __future__ import annotations

from typing import Mapping, TypedDict


class ReactionRoleReaction(TypedDict):
    id: int
    reaction_role: int
    message_id: int
    guild_id: int
    channel_id: int
    role_id: int
    emoji: str


class ReactionRoleCached(TypedDict):
    message_id: int
    guild_id: int
    channel_id: int
    reaction_roles: Mapping[str, ReactionRoleReaction]
