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

import logging
from typing import (
    List,
    Optional,
)

import discord
from discord.ext import commands

from utils import BaseCog, _check_for_hierarchy, _format_dt
from utils.context import Context, tick
from utils.time import UserFriendlyTime, human_timedelta, human_join
from utils.timer import Timer
from utils.errors import MemberAlreadyLocked


log = logging.getLogger(__name__)


class Lockdowns(BaseCog):
    
    @commands.group(name='lockdown', description='Lock down commands.', invoke_without_command=True, aliases=['lock', 'l'])
    async def lockdown(
        self, 
        ctx: Context, 
        members: List[discord.Member] = commands.parameter(converter=commands.Greedy[discord.Member]), 
        *,
        time: UserFriendlyTime(default='No reason given.') # type: ignore    
    ) -> Optional[discord.Message]:
        """|coro|
        
        Lockdown a member for a specific reason and time. If no time is given, they are locked
        permanently.
        
        Parameters
        ----------
        members: List[:class:`discord.Member`]
            The member to lockdown. You can mention one member or many, it's up to you.
            For example `fury.lockdown @Timmy @Tommy 1h for being annoying`.
        time: Optional[:class:`str`]
            The time and reason for the lockdown. If no time is provided, the member will not be removed
            from lockdown until the ``freedom`` command is used.
            
            Example: `fury.lockdown @Chai 1h being annoying`, `fury.lockdown @Chai Tomorrow at 2pm being annoying`
        """
        
        if ctx.invoked_subcommand:
            return

        statuses = []
        for member in members:
            if not _check_for_hierarchy(member):
                statuses.append(tick(False, f'{member.mention}: Hierarchy issue.'))
                
            try:
                timer = await self.bot.lockdown(member, reason=time.arg, time=time.dt, moderator=ctx.author.id) 
            except MemberAlreadyLocked:
                statuses.append(tick(False, f'{member.mention}: Already locked.'))
            else:
                if not timer:
                    statuses.append(tick(None, label=f'{member.mention}: Something borked?'))
                    continue
                
                statuses.append(tick(True, f'{member.mention}'))
                
        return await ctx.send(f'Locked:\n' + '\n'.join(statuses))
        
    @lockdown.command(name='info')
    async def lockdown_info(self, ctx: Context, member: discord.Member) -> Optional[discord.Message]:
        """|coro|
        
        Used to get information about a member's current lockdown.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to get information about.
        """
        record = await self.bot.is_locked(member, return_record=True)
        if not record:
            return await ctx.send(f'{member.mention} is not locked.')
        
        timer = Timer(record=record)
        
        embed = self.bot.Embed(
            title='Lockdown Info',
            description=f'Member {member.mention} was locked {timer.human_delta(created=True)} ago ({timer.human_timestamp(created=True)})',
        )
        embed.add_field(name='Reason', value=timer.kwargs['reason'], inline=False)
        embed.add_field(name='Expires', value=timer.human_timestamp(), inline=False)
        embed.add_field(name='Role(s) Affected', value=human_join([f'<@&{id}' for id in timer.kwargs['roles']], final='and') or 'No Roles.')
        embed.add_field(name='Channel(s) Affected', value=human_join([f'<#{id}' for id in timer.kwargs['channels']], final='and') or 'No Channels.')
        embed.set_footer(text='You can do "fury.unlock" to unlock them.')
        return await ctx.send(embed=embed)
        
    
    @lockdown.command(name='remove', description='Remove a lockdown from a member.')
    async def lockdown_remove(self, ctx: Context, member: discord.Member) -> None:
        """|coro|
        
        Remove a lockdown from a member.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to remove the lockdown from.
        """
        await self.freedom(ctx, member)
        
    @lockdown.command(name='history', description='Get the history of a member\'s lockdowns.')
    async def lockdown_history(self, ctx: Context, member: discord.Member) -> discord.Message:
        """|coro|
        
        Get the lockdown history of a member in the server.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to get the history of. Must be a member of the server. Mention them for this argument.
        """
        timers = await self.bot.fetch_timers('WHERE extra#>\'{kwargs, member}\' = $1 AND extra#>\'{kwargs, type}\' = $2', member.id, 'lockdowns')
            
        if not timers:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} has no lockdown history!'
            ))
        
        embed = self.bot.Embed(
            title=f'Lockdown History for {member}',
            description='This is a list of all the lockdowns that have been placed on this member.',
            author=member
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name='Total Lockdowns', value=f'{len(timers)} lockdowns total.', inline=False)
        
        time = None
        first = None
        for timer in timers:
            if timer.dispatched:
                if not time:
                    time = timer.expires - timer.created_at
                else:
                    time += timer.expires - timer.created_at
            
            if not first:
                first = timer.created_at
            else:
                if timer.created_at < first:
                    first = timer.created_at
        
        if embed.description and time and first: # Type checker
            embed.description += f'\n\nMember {member.mention} has spent {_format_dt(time)} in lockdown over the span of {human_timedelta(first, suffix="")}' 
        
        reasons = ['{0}: {1}'.format(index, timer.kwargs.get('reason') or 'No reason provided') for index, timer in enumerate(timers)]
        embed.add_field(name='Lockdown Reasons', value='\n'.join(reasons), inline=False)
        
        active: Optional[Timer] = discord.utils.get(timers, dispatched=False)
        if active:
            data = [
                f'Expires: {_format_dt(active.expires) if active.expires else "Does not expire."}',
                f'Created: {_format_dt(active.created_at)}',
            ]
            embed.add_field(name='Active Lockdown', value='\n'.join(data), inline=False)
        
        return await ctx.send(embed=embed)
        
    @lockdown.command(name='clear', description='Clear all lockdown history from a member.')
    async def lockdown_clear(self, ctx: Context, member: discord.Member) -> None:
        """|coro|
        
        Clear the lockdown history of a member in the server.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to clear the history of. Must be a member of the server. Mention them for this argument.
        """
        
        embed = self.bot.Embed(
            title='Are you sure?',
            description=f'This will clear **all** lockdown history on {member.mention}. This can not be undone.'
        )
        
        value = await ctx.get_confirmation(embed=embed)
        if not value:
            return
        
        async with self.bot.safe_connection() as conn:
            await conn.fetchrow('DELETE FROM timers WHERE extra#>\'{kwargs, member}\' = $1 AND extra#>\'{kwargs, type}\' = $2', member.id, 'lockdowns')
        
        embed = self.bot.Embed(
            title='Done',
            description=f'I have cleared all lockdown history for {member.mention}.',
            author=member
        )
        return await ctx.send(embed=embed, view=None) # type: ignore
    
    @commands.command(name='lockdowns', description='View the past lockdowns on a member.')
    async def lockdowns(self, ctx: Context, member: discord.Member) -> discord.Message:
        """|coro|
        
        Get the lockdown history of a member in the server.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to get the history of. Must be a member of the server. Mention them for this argument.
        """
        return await self.lockdown_history(ctx, member)
    
    @commands.command(name='freedom', description='Remove a lockdown from a member.', aliases=['unlock', 'unlockdown'])
    async def freedom(self, ctx: Context, member: discord.Member):
        """|coro|
        
        Unlock a member from lockdown.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to unlock. Must be a member of the server. Mention them for this argument.
        """
        
        hierarchy_check = _check_for_hierarchy(member)
        if not hierarchy_check:
            return await ctx.send(f'I can not do this as {member.mention} is higher than or equal to me in role set.')
        
        timer = await self.bot.freedom(member)
        assert timer is not None
        
        embed = self.bot.Embed(
            title='Member Unlocked',
            description=f'{member.mention} has been unlocked from their lockdown.',
        )
        embed.add_field(name='Reason', value=timer.kwargs['reason'], inline=False)
        embed.add_field(name='Was Set to Expire', value=timer.human_timestamp(), inline=False)
        embed.add_field(name='Role(s) Affected', value=human_join([f'<@&{id}>' for id in timer.kwargs['roles']], final='and') or 'No Roles.')
        embed.add_field(name='Channel(s) Affected', value=human_join([f'<#{id}>' for id in timer.kwargs['channels']], final='and') or 'No Channels.')
        
        return await ctx.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_lockdowns_timer_complete(self, timer: Timer) -> None:
        """|coro|
        
        A coroutine that is called when a Lockdown timer is complete. This means
        it's time to unlock the member.
        
        Parameters
        ----------
        timer: :class:`Timer`
            The timer that is complete.
        """
        await self.bot.wait_until_ready()
        
        guild = self.bot.fury_guild
        if not (member := getattr(timer, 'member', None)):
            member = guild.get_member(timer.kwargs['member']) or await guild.fetch_member(timer.kwargs['member'])
        
        log.info(f'On lockdowns timer complete for member {member}')
        
        # Restore roles here
        channels = timer.kwargs['channels']
        roles = timer.kwargs['roles']
        
        for channel in channels:
            channel = guild.get_channel(channel)
            if not channel:
                continue
            
            overwrites = channel.overwrites
            if member in overwrites:
                overwrites[member].update(view_channel=True)
                
            await channel.edit(overwrites=overwrites) # type: ignore
        
        keep_roles: List[Union[discord.Object, discord.Role]] = member.roles # type: ignore
        keep_roles_fmt = [kr.id for kr in keep_roles]
        try:
            keep_roles.remove(self.bot.get_lockdown_role())
        except:
            pass
        
        keep_roles.extend([discord.Object(id=r) for r in roles if r not in keep_roles_fmt]) # type: ignore
        await member.edit(roles=keep_roles)
        
        embed = self.bot.Embed(
            title='Lockdown Ended',
            description='Your lockdown has ended! You access tot he server has been restored. Feel free to review the rules and enjoy the server.'
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_footer(text=f'ID: {member.id}')
        embed.add_field(name='Locked Since', value=f'{human_timedelta(timer.created_at)} ({discord.utils.format_dt(timer.created_at)}).')
        await self.bot.send_to(member, embed=embed)