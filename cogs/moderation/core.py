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
import datetime
from collections import Counter
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    List,
    Optional,
    Union
)

import discord
from discord.ext import commands

from utils import BaseCog, clamp
from utils.context import Context, tick
from utils.time import UserFriendlyTime

    
log = logging.getLogger(__name__)

MISSING = discord.utils.MISSING

def _limit_cleaning():
    async def wrapped(ctx: Context) -> bool:
        if not isinstance(ctx.author, discord.Member):
            raise commands.NoPrivateMessage('This command can not be used in private messages.')
        
        if not ctx.author.guild_permissions.manage_messages:
            raise commands.MissingPermissions(['manage_messages'])
        
        return True
    
    return commands.check(wrapped)


ClampParameter: Any = commands.parameter(default=100, converter=partial(clamp, max_number=100, min_number=1))


class CoreModeration(BaseCog):
    
    async def _do_cleaning(
        self, 
        ctx: Context,
        channel: discord.abc.Messageable, 
        /,
        *args,
        predicate: Callable[[discord.Message], bool],
        **kwargs: Any
    ) -> None:
        if not (purger := getattr(channel, 'purge', None)):
            raise RuntimeError(f'{channel.__class__.__name__} does not support purging.')
        
        counter = Counter()
        messages = await purger(check=predicate, *args, **kwargs)
        
        for message in messages:
            counter[message.author] += 1
        
        fmt = '\n'.join(f'**{str(author)}**: {count}' for author, count in counter.most_common())
        await ctx.send(f'Deleted {counter.total()} messages.\n\n{fmt}', delete_after=5)
    
    @commands.group(
        name='cleanup',
        brief='Cleanup Messages',
        description='Cleanup messages from the channel.',
        invoke_without_command=True,
        aliases=['purge', 'prune', 'clear']
    )
    @_limit_cleaning()
    async def cleanup(
        self, 
        ctx: Context, 
        channel: discord.TextChannel = commands.parameter(
            default=lambda ctx: ctx.channel, 
            converter=Optional[Union[discord.TextChannel, discord.Thread]]
        ),
        member: discord.Member = commands.parameter(
            default=lambda ctx: ctx.guild.me, 
            converter=Optional[discord.Member]
        ),
        count: int = ClampParameter, 
    ) -> None:
        """|coro|
        
        Cleanup messages from the channel.
        
        Parameters
        ----------
        channel: Optional[Union[:class:`discord.TextChannel`, :class:`discord.Thread`]]
            The channel to cleanup in, defaults to the current channel.
        member: Optional[:class:`discord.Member`]
            The member to cleanup messages from, defaults to FuryBot.
        count: :class:`int`
            The number of messages to delete, the max is 100.
        """
        if ctx.invoked_subcommand:
            return
        
        print(channel, member, count)
        
        def predicate(message: discord.Message) -> bool:
            assert message.guild is not None
            
            if member == message.guild.me: 
                assert isinstance(self.bot.command_prefix, tuple)
                
                if message.content and message.content.startswith(self.bot.command_prefix):
                    return True
                
            return message.author == member
            
        await self._do_cleaning(ctx, channel, predicate=predicate, limit=count)
        
    @commands.command(
        name='ban',
        brief='Ban a user from the server.',
        description='Ban a member from the server.',
        aliases=['banish']
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self, 
        ctx: Context,
        members: commands.Greedy[discord.Object], 
        delete_message_days: int = 1,
        *, 
        reason: Optional[str] = None
    ) -> None:
        """|coro|
        
        Used to ban a member from the server.
        
        Parameters
        ----------
        members: List[:class:`discord.Object`]
            A list of members to ban. If multiple members are provided, they will be banned in sequence.
            Example: `fury.ban @Timmy @Tommy`
        delete_message_days: :class:`int`
            The number of days to delete messages from the user.
        reason: Optional[:class:`str`]
            The reason for the ban.
        """
        assert ctx.guild is not None
        
        statuses = []
        for member in members:
            try:
                await ctx.guild.ban(
                    member, 
                    reason=reason, 
                    delete_message_days=delete_message_days
                )
            except Exception as exc:
                statuses.append(tick(False, label=f'<@{member.id}>: {exc.__class__.__name__}'))
            else:
                statuses.append(tick(True, label=f'<@{member.id}>'))
        
        await ctx.send('Banned:\n' + '\n'.join(statuses))
        
    @commands.command(
        name='kick',
        brief='Kick a user from the server.',
        description='Kick a member from the server.',
        aliases=['boot', 'booty']
    )
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self,
        ctx: Context, 
        members: commands.Greedy[discord.Member],
        *, 
        reason: Optional[str] = None
    ) -> None:
        """|coro|
        
        Used to kick a member from the server.
        
        Parameters
        ----------
        members: List[:class:`discord.Member`]
            A list of members to kick. If multiple members are provided, they will be kicked in sequence.
            Example: `fury.kick @Timmy @Tommy`
        reason: Optional[:class:`str`]
            The reason for the kick.
        """
        assert ctx.guild is not None
        
        statuses = []
        for member in members:
            try:
                await ctx.guild.kick(member, reason=reason, )
            except Exception as exc:
                statuses.append(tick(False, label=f'{member.mention}: {exc.__class__.__name__}'))
            else:
                statuses.append(tick(True, label=f'{member.mention}'))
        
        await ctx.send(
            'Kicked:\n' + '\n'.join(statuses), 
            allowed_mentions=discord.AllowedMentions(users=False)
        )
        
    @commands.command(
        name='timeout',
        brief='Timeout a user from the server.',
        description='Timeout a member from the server.',
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(
        self, 
        ctx: Context, 
        members: commands.Greedy[discord.Member], 
        *, 
        time: UserFriendlyTime = commands.parameter(converter=UserFriendlyTime(default='...')) 
    ) -> Optional[discord.Message]:
        
        if time.dt - ctx.message.created_at > datetime.timedelta(days=28):
            return await ctx.send('You cannot timeout a user for more than a week.')
        
        statuses = []
        for member in members:
            try:
                await member.timeout(time.dt, reason=time.arg)
            except Exception as exc:
                statuses.append(tick(False, label=f'{member.mention}: {exc.__class__.__name__}'))
            else:
                statuses.append(tick(True, label=f'{member.mention}'))
        
        return await ctx.send(
            'Timed out:\n' + '\n'.join(statuses), 
            allowed_mentions=discord.AllowedMentions(users=False)
        )