import asyncio
import logging

import discord
from discord.ext import commands

from typing import TYPE_CHECKING, List, Optional, Union

from cogs.utils.types import Reasons
from cogs.utils.errors import NotLocked
from cogs.utils.constants import (
    BYPASS_FURY,
    LOCKDOWN_NOTIFICATIONS_ROLE,
    LOCKDOWN_ROLE,
    FURY_GUILD
)

if TYPE_CHECKING:
    from bot import FuryBot


def moderator_check(member):
    return True if BYPASS_FURY in [role.id for role in member.roles] else False


def mention_staff(guild):
    notis_role = discord.utils.get(guild.roles, id=LOCKDOWN_NOTIFICATIONS_ROLE)
    return notis_role.mention


class BaseEvent(commands.Cog):
    __slots__ = ('bot', 'profanity', 'extractor', 'CUSTOM_WORDS')

    def __init__(self, bot: 'FuryBot') -> None:
        self.bot: FuryBot = bot
        self.profanity = bot.profanity
        self.extractor = bot.extractor


    async def contains_profanity(self, message: str) -> bool:
        if not self.profanity:
            return False
        return await self.bot.loop.run_in_executor(None, self.profanity.contains_profanity, message)

    async def censor(self, message: str) -> str:
        if not self.profanity:
            return 'Profanity filter not loaded'
        return await self.bot.loop.run_in_executor(None, self.profanity.censor, message)

    async def get_links(self, message: str) -> Union[None, List[str]]:
        if not self.extractor:
            return None
        data = await asyncio.gather(*[self.bot.loop.run_in_executor(None, self.extractor.gen_urls, message)])
        return list(data[0]) if data else None

    def is_locked(self, member: Union[discord.Member, discord.User, int]) -> bool:
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member
        return True if self.bot.locked_out.get(member) is not None else False

    def is_valid_unlock(self, member: Union[discord.Member, discord.User, int], reason: Reasons) -> bool:
        """Returns true if the extra section on the users lock data is None."""
        member = member.id if isinstance(member, (discord.Member, discord.User)) else member

        extra = self.bot.locked_out[member]['extra']
        if not extra:
            return True
        if len(extra) == 1 and extra[
            0] == reason:  # The only reason for being locked is the reason we're unlocking them for.
            self.bot.locked_out[member]['extra'] = []
            return True
        return False

    def increment_extra_if_necessary_for(self, member: Union[discord.Member, discord.User], reason: Reasons) -> None:
        """
        Increment the "extra" section of a locked out member if nessecary.
        """
        data = self.bot.locked_out[member.id]['extra']
        if reason not in data:
            self.bot.locked_out[member.id]['extra'].append(reason)

    async def handle_roles(self, operation: str, member: discord.Member, reason: Optional[str] = None,
                           atomic: Optional[bool] = False) -> None:
        attr = getattr(member, operation)
        role = member.guild.get_role(LOCKDOWN_ROLE)
        if not role:
            roles = await member.guild.fetch_roles()
            role = [role for role in roles if role.id == LOCKDOWN_ROLE][0]

        if role in member.roles:  # Member is already locked down.
            return None

        logging.info(f"ADDING ROLE: Adding Role {role} to {str(member)}")
        return await attr(*[role], reason=reason, atomic=atomic)

    async def add_lockdown_for(
        self,
        member: Union[discord.Member, discord.User],
        *,
        enum_reason: Reasons,
        reason: Optional[str] = "Bad status",
        guild: Optional[discord.Guild] = None,
        bad_status: Optional[str] = None,
        raw_status: Optional[str] = None
    ) -> None:
        """
        Lock a member out for the first time. 
        """
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))

        await self.handle_roles('add_roles', member, reason=reason, atomic=False)

        packet = {
            'member_id': member.id,
            'extra': [enum_reason]
        }
        if bad_status:
            packet['bad_status'] = bad_status
        if raw_status:
            packet['raw_status'] = raw_status
        self.bot.locked_out[member.id] = packet

        logging.warning(f"ADDED LOCKDOWN: Lockdown added to {str(member)} for: {reason}")
        return

    async def remove_lockdown_for(
        self,
        member: Union[discord.Member, discord.User],
        *,
        guild: Optional[discord.Guild] = None,
        reason: Optional[str] = 'status'
    ) -> discord.Embed:
        """
        Remove a lockdown for a member.
        """
        if isinstance(member, discord.User):
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))

        try:
            del self.bot.locked_out[member.id]
        except KeyError:
            raise NotLocked(f'{member.mention} is not locked, can not unlock them')

        await self.handle_roles('remove_roles', member, reason=f'Member fixed {reason}', atomic=False)

        e = self.bot.Embed()

        e.title = 'Thank you.'
        e.description = 'Your lockdown role was removed.'
        try:
            await member.send(embed=e)
            could_dm = True
        except (discord.Forbidden, discord.HTTPException):
            could_dm = False

        e.title = f"Member fixed their {reason}."
        e.description = f'**{str(member)} ({member.mention})** has fixed their {reason}. Their access to the server has been fixed.'
        e.add_field(name='Could DM?', value=could_dm)
        await self.bot.send_to_log_channel(embed=e, content=mention_staff(member.guild))

        logging.info(f"REMOVED LOCKDOWN: Lockdown removed from {str(member)} after fixing their {reason}.")
        return e

    async def lockdown_if_necessary_for(
            self,
            member: Union[discord.Member, discord.User],
            *,
            reason: Reasons,
            raw_reason: str = None,
            bad_status: Optional[str] = None,
            raw_status: Optional[str] = None
    ) -> None:
        """
        A more "blanket" lockdown func. This wil lockout the user if nesscary, or increment their lockout if not.
        """
        if isinstance(member, discord.User):
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))

        if self.is_locked(member):  # Member is already locked, increment their data.
            return self.increment_extra_if_necessary_for(member, reason)

        # Member is not locked if we get here.
        await self.add_lockdown_for(
            member,
            enum_reason=reason,
            reason=raw_reason,
            bad_status=bad_status,
            raw_status=raw_status
        )

    async def remove_lockdown_if_necessary_for(
            self,
            member: Union[discord.Member, discord.User],
            reason: Reasons,
            raw_reason: str = None
    ) -> None:
        """
        A more "blanket" unlock func. This wil lockout the user if nesscary, or increment their lockout if not.
        """
        if isinstance(member, discord.User):
            guild = self.bot.get_guild(FURY_GUILD) or (await self.bot.fetch_guild(FURY_GUILD))
            member = guild.get_member(member.id) or (await guild.fetch_member(member.id))

        if self.is_locked(member):
            if self.is_valid_unlock(member,
                                    reason):  # Member has no outstanding locks OR the only lock they have is the one they're getting removed for.
                await self.remove_lockdown_for(member, reason=raw_reason)
            else:  # Member is locked for more then one reason, we need to remove this specific one.
                if reason in self.bot.locked_out[member.id]['extra']:
                    self.bot.locked_out[member.id]['extra'].remove(reason)  # remove the reason
