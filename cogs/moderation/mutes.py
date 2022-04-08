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
    TYPE_CHECKING,
    Optional,
)

import discord
from discord.ext import commands

from utils import BaseCog, _format_dt, constants
from utils.context import Context
from utils.time import UserFriendlyTime, human_timedelta, human_join
from utils.timer import Timer

if TYPE_CHECKING:
    from asyncpg import Connection, Record
    
log = logging.getLogger(__name__)
    
    
class Mutes(BaseCog):
    
    async def _get_mute(self, member: discord.Member, *, connection: Optional[Connection] = None) -> Record:
        """|coro|
        
        Used to get the mute record for a member.
        
        Parameters
        ----------
        member: :class:`discord.Member`
            The member to get the mute record for.
        connection: Optional[:class:`asyncpg.Connection`]
            The connection to use. If not provided, a new connection will be created.
        """
        
        query = 'SELECT * FROM timers WHERE extra#>\'{kwargs, member}\' = $1 AND extra#>\'{kwargs, type}\' = $2 AND dispatched = $3'
        
        if connection:
            data = await connection.fetchrow(query, member.id, 'mute', False)
        else:
            async with self.bot.safe_connection() as conn:
                data = await conn.fetchrow(query, member.id, 'mute', False)
                
        return data
    
    # Muting members
    @commands.group(name='mute', description='Mute members.')
    async def mute(self, ctx: Context, member: discord.Member, *, time: UserFriendlyTime(default='No reason specified.')) -> Optional[discord.Message]: # type: ignore
        """|coro|
        
        Used to mute a member from the server. This will limit them from speaking in any text channels
        within the server.
        
        Parameters
        ----------
        member: discord.Member
            The member to mute. Must be a member of the server. Mention them for this argument.
        time: Optional[str]
            The time and reason for the lockdown. If no time is provided, the member will not be removed
            from lockdown until the ``freedom`` command is used.
            
            Example: `fury.lockdown @Chai 1h being annoying`, `fury.lockdown @Chai Tomorrow at 2pm being annoying`
        """
        if ctx.invoked_subcommand:
            return
        
        # Make type checker happy
        if not ctx.guild:
            return
        
        data = await self._get_mute(member)
        
        if data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is already muted.',
            ))
        
        original_roles = [r.id for r in member.roles if r.is_assignable()]
        
        channels = []
        for channel in ctx.guild.text_channels:
            overwrites = channel.overwrites
            if overwrites.get(member):
                specific = discord.utils.find(lambda e: e[0] == 'send_messages' and e[1] == True, overwrites.items())
                if specific:
                    overwrites[member].update(send_messages=False)
                    await channel.edit(overwrites=overwrites) # type: ignore
                    channels.append(channel.id)
        
        muted_role = ctx.guild.get_role(constants.MUTED_ROLE)
        if muted_role is None:
            raise RuntimeError('Muted role not found.')
        
        kr = [muted_role]
        kr.extend([r for r in member.roles if not r.is_assignable()])
        
        try:
            await member.edit(roles=kr)
        except:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'I can not edit the roles on {member.mention}.'
            ))
    
        timer = await self.bot.create_timer(
            time.dt,
            'mutes',
            precise=False,
            roles=original_roles,
            channels=channels,
            member=member.id,
            moderator=ctx.author.id,
            type='mute'
        )
        
        embed = self.bot.Embed(title='Muted', description=f'{member.mention} has been muted.')
        embed.add_field(name='Reason', value=time.arg if time else 'No reason provided.', inline=False)
        embed.add_field(name='Expires', value=_format_dt(timer.expires) if timer.expires else "Does not expire.", inline=False)
        embed.add_field(name='Moderator', value=ctx.author.mention, inline=False)
        embed.add_field(name='Role(s) Affected', value=', '.join([f'<@&{r}>' for r in original_roles] or ['No roles.']), inline=False)
        embed.add_field(name='Channel(s) Affected', value=', '.join([f'<#{c}>' for c in channels] or ['No channels.']), inline=False)
        return await ctx.send(embed=embed) 
                
    @mute.command(name='remove', description='Remove a mute on a member.', aliases=['delete', 'unmute'])
    async def mute_remove(self, ctx: Context, member: discord.Member) -> discord.Message:
        """|coro|
        
        Remove a mute on a member.
        
        Parameters
        ----------
        member: discord.Member
            The member to remove the mute from. Must be a member of the server. Mention them for this argument.
        """
        async with self.bot.safe_connection() as conn:
            data = await self._get_mute(member)

            if data is None:
                return await ctx.send(embed=self.bot.Embed(
                    title='Oh no!',
                    description=f'{member.mention} is not muted.'
                ))
                
            await conn.execute('UPDATE timers SET dispatched = $1 WHERE id = $2', True, data['id'])

        temp = Timer(record=data)
        temp.member = member
        await self.on_mutes_timer_complete(temp)
        
        embed = self.bot.Embed(
            title='Mute removed',
            description=f'{member.mention} has been unmuted.'
        )
        embed.add_field(name='Total Mute Time', value=f'{member.mention} was muted for {human_timedelta(temp.created_at)}')
        
        return await ctx.send(embed=embed)
    
    @mute.command(name='current', description='Get info on a current mute.')
    async def mute_current(self, ctx, member: discord.Member) -> None:
        """|coro|
        
        Get some information on a current mute that a member has.
        
        Parameters
        ----------
        member: discord.Member
            The member to get the mute info on. Must be a member of the server. Mention them for this argument.
        """
        data = await self._get_mute(member)
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is not muted.'
            ))
            
        temp = Timer(record=data)
        
        embed = self.bot.Embed(
            title=f'Mute info on {str(member)}',
            description=f'{member.mention} is muted! They will be unmuted at {_format_dt(temp.expires)}.'
        )
        embed.add_field(name='Created At', value=discord.utils.format_dt(temp.created_at, style='F'), inline=False)
        
        expires_fmt = f'Expires in {human_timedelta(expires)} ({_format_dt(expires)})' if (expires := temp.expires) else 'Does not expire.'
        embed.add_field(name='Expires', value=expires_fmt, inline=False)
        embed.add_field(name='Mute Reason', value=temp.kwargs.get('reason', 'None given.'), inline=False)
        embed.add_field(name='Moderator', value=f'<@{moderator}>' if (moderator := temp.kwargs.get('moderator')) else 'No moderator given.', inline=False)
        embed.add_field(
            name='Channel(s) Affected', 
            value=human_join([f'<#{id}>' for id in temp.kwargs['channels']] or ['No channels affected.'], final='and'), 
            inline=False
        )
        embed.add_field(
            name='Role(s) Affected', 
            value=human_join([f'<@&{id}>' for id in temp.kwargs['roles']] or ['No roles removed.'], final='and'), 
            inline=False
        )
        return await ctx.send(embed=embed)
    
    @mute.command(name='history', description='List the mute history of a member.')
    async def mute_history(self, ctx, member: discord.Member) -> None:
        """|coro|
        
        Used to get the mute history of a member.
        
        Parameters
        ----------
        member: discord.Member
            The member to get the mute history of. Must be a member of the server. Mention them for this argument.
        """
        async with self.bot.safe_connection() as conn:
            data = await conn.fetch('SELECT * FROM mutes WHERE member = $1 ORDER by created', member.id)
        
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='No mute history!',
                description=f'{member.mention} has no mute history.'
            ))
        
        embed = self.bot.Embed(title='Mute History', description=f'{member.mention} has a mute history {len(data)} entries long.')
        for index, entry in enumerate(data):
            # TODO: Add a way to see the moderator and reason
            new = Timer(record=entry)
            
            fmt = f"**Reason**: {new.kwargs['reason']}\n" \
                f"**Created**: {discord.utils.format_dt(new.created_at, style='F')}\n" \
                f"**Expires**: {discord.utils.format_dt(new.expires, style='F') if new.expires else 'Never'}\n"
            
            embed.add_field(name=f'Mute {index+1}', value=fmt, inline=False)
        
        return await ctx.send(embed=embed)
    
    @commands.command(name='unmute', description='Unmute a member.')
    async def unmute(self, ctx: Context, member: discord.Member) -> None:
        await self.mute_remove(ctx, member)
        
    @commands.Cog.listener()
    async def on_mutes_timer_complete(self, timer: Timer) -> None:
        """|coro|
        
        Called when an existing mute on a member is expired. This will unmute them.
        
        Parameters
        ----------
        timer: :class:`Timer`
            The timer that expired.
        """
        
        await self.bot.wait_until_ready()
        
        guild = self.bot.get_guild(constants.FURY_GUILD)
        if guild is None:
            raise RuntimeError('Fury guild not found.')
        
        member = guild.get_member(timer.kwargs['member']) or await guild.fetch_member(timer.kwargs['member'])
        log.info(f'On mutes timer complete for member {member}')
        
        for channel_id in timer.kwargs['channels']:
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            overwrites = channel.overwrites
            if overwrites.get(member):
                overwrites[member].update(send_messages=True)
                await channel.edit(overwrites=overwrites) # type: ignore
                
        roles = timer.kwargs['roles']
        objs = [discord.Object(id=r) for r in roles]
        await member.edit(roles=objs)