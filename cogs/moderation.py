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
    Optional
)

import discord
from discord.ext import commands

from utils import timer, constants, BaseCog
from utils.errors import ProfanityFailure
from utils.context import Context
from utils.time import (
    human_timedelta, 
    human_join, 
    UserFriendlyTime,
    td_format
)

if TYPE_CHECKING:
    from bot import FuryBot
    import datetime
    from asyncpg import Record, Connection
    
log = logging.getLogger(__name__)

MISSING = discord.utils.MISSING
    
__all__ = (
    'Moderation',
)

def _format_dt(dt: datetime.datetime) -> str:
    try:
        return discord.utils.format_dt(dt, style='F')
    except OverflowError:
        return 'Time is too far in the future.'
    
def _check_for_hierarchy(member: discord.Member) -> bool:
    guild = member.guild
    me = guild.me
    
    if member.top_role >= me.top_role:
        return False
    if member == me:
        return False
    if guild.owner == member:
        return False
    
    return True


class Moderation(BaseCog):
    """The main Moderation cog. Contains all moderation based commands.
    These commands can only be used by authorized members. If you are not authorized, you will be kicked from the server... jokes! :D
    """
    
    async def cog_check(self, ctx: Context) -> bool:
        if isinstance(ctx.author, discord.User):
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        
        authorized = (constants.CAPTAIN_ROLE, constants.MOD_ROLE, constants.COACH_ROLE, constants.BYPASS_FURY)
        result = any(r.id in authorized for r in ctx.author.roles)
        if not result:
            raise commands.MissingPermissions(['server_moderator'])
        
        return True
        
    @commands.group(name='lockdown', description='Lock down commands.', invoke_without_command=True, aliases=['lock', 'l'])
    async def lockdown(
        self, 
        ctx: Context, 
        member: discord.Member, 
        *,
        time: UserFriendlyTime(default='...') = None # type: ignore    
    ) -> Optional[discord.Message]:
        """|coro|
        
        Lockdown a member for a specific reason and time. If no time is given, they are locked
        permanently.
        
        Parameters
        ----------
        member: discord.Member
            The member to lockdown. Must be a member of the server. Mention them for this argument.
        time: Optional[str]
            The time and reason for the lockdown. If no time is provided, the member will not be removed
            from lockdown until the ``freedom`` command is used.
            
            Example: `fury.lockdown @Chai 1h being annoying`, `fury.lockdown @Chai Tomorrow at 2pm being annoying`
        """
        
        if ctx.invoked_subcommand:
            return

        hierarchy_check = _check_for_hierarchy(member)
        if not hierarchy_check:
            return await ctx.send(f'I can not do this as {member.mention} is higher than or equal to me in role set.')
                
        if time is None:
            result = await self.bot.lockdown(member, reason='None specified.', moderator=ctx.author.id) 
        else:
            result = await self.bot.lockdown(member, reason=time.arg, time=time.dt, moderator=ctx.author.id) 
        
        if not result:
            embed = self.bot.Embed(
                title='Oh no!',
                description='Something went wrong while trying to lockdown the member. You will need to lock them manually, or try again.',
            )
        else:
            embed = self.bot.Embed(
                title='Success!',
                description=f'I have locked down {member.mention} for reason "{time.arg if time else "None specified"}".',
            )
            embed.add_field(name='Note:', value='They have been given the Lockdown Role, and all their previous roles have been removed. You can do `fury.unlock` to unlock them.')
            
        return await ctx.send(embed=embed)
    
    @lockdown.command(name='remove', description='Remove a lockdown from a member.')
    async def lockdown_remove(self, ctx: Context, member: discord.Member) -> None:
        """|coro|
        
        Remove a lockdown from a member.
        
        Parameters
        ----------
        member: discord.Member
            The member to remove the lockdown from.
        """
        
        await self.freedom(ctx, member)
        
    @lockdown.command(name='history', description='Get the history of a member\'s lockdowns.')
    async def lockdown_history(self, ctx: Context, member: discord.Member) -> discord.Message:
        """|coro|
        
        Get the lockdown history of a member in the server.
        
        Parameters
        ----------
        member: discord.Member
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
            embed.description += f'\n\nMember {member.mention} has spent {td_format(time)} in lockdown over the span of {human_timedelta(first, suffix="")}' 
        
        reasons = ['{0}: {1}'.format(index, timer.kwargs.get('reason') or 'No reason provided') for index, timer in enumerate(timers)]
        embed.add_field(name='Lockdown Reasons', value='\n'.join(reasons), inline=False)
        
        active: Optional[timer.Timer] = discord.utils.get(timers, dispatched=False)
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
        member: discord.Member
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
        member: discord.Member
            The member to get the history of. Must be a member of the server. Mention them for this argument.
        """
        return await self.lockdown_history(ctx, member)
    
    @commands.command(name='freedom', description='Remove a lockdown from a member.', aliases=['unlock', 'unlockdown'])
    async def freedom(self, ctx: Context, member: discord.Member):
        """|coro|
        
        Unlock a member from lockdown.
        
        Parameters
        ----------
        member: discord.Member
            The member to unlock. Must be a member of the server. Mention them for this argument.
        """
        
        hierarchy_check = _check_for_hierarchy(member)
        if not hierarchy_check:
            return await ctx.send(f'I can not do this as {member.mention} is higher than or equal to me in role set.')
        
        await self.bot.freedom(member)
        
        return await ctx.send(embed=self.bot.Embed(
            title='Success!',
            description=f'I have freed {member.mention} from lockdown.'
        ))

    @commands.group(name='profanity', description='Handle the profanity filter', invoke_without_command=True, aliases=['p'])
    async def profanity(self, ctx: Context, word: str) -> None:
        """|coro|
        
        A command group to handle and interact with the profanity filter.

        Invoking without a command checks if a word is profane.
        
        Parameters
        ----------
        word: str
            The word to check if it is profane.
        """
        
        if ctx.invoked_subcommand:
            return
        
        await self.wordset_contains_profanity(ctx, word)
    
    @profanity.command(name='remove', description='Make a word bad word a good word')
    async def profanity_remove(self, ctx: Context, word: str) -> discord.Message:
        """|coro|
        
        Used to remove a profane word from the profanity filter.
        
        Parameters
        ----------
        word: str
            The word to remove from the profanity filter.
        """
        
        try:
            await self.bot.add_word_to('clean', word, wrapper=self.bot.wrap)
        except ProfanityFailure as exc:
            raise exc
        
        return await ctx.reply(f'Removed "{word}" from the list of banned words')
    
    @profanity.command(name='add' ,description='Make a word a profanity word.')
    async def wordset_add(self, ctx: Context, word: str) -> discord.Message:
        """|coro|
        
        Used to add a profane word to the profanity filter.
        
        Parameters
        ----------
        word: str
            The word to add to the profanity filter.
        """
        try:
            await self.bot.add_word_to('profanity', word, wrapper=self.bot.wrap)
        except ProfanityFailure as exc:
            raise exc
        
        return await ctx.reply(f'Added {word} to the list of banned words')
    
    @profanity.command(name='contains_profanity', description='Determine if a word contains profanity.', aliases=['contains', 'c'])
    async def wordset_contains_profanity(self, ctx: Context,  word: str) -> discord.Message:
        """|coro|
        
        Used to determine if a word is profane.
        
        Parameters
        ----------
        word: str
            The word to check if it is profane.
        """
        check = await self.bot.contains_profanity(word)
        fmt = ' not' if check is False else ''
        return await ctx.reply(f"Word {word} does{fmt} contain profanity.")
    
    @profanity.command(name='censor', description='Censor a sentence.' )
    async def wordset_censor(self, ctx: Context, sentence: str) -> discord.Message:
        """|coro|
        
        Used to censor a sentence to check if it contains profanity.
        
        Parameters
        ----------
        sentence: str
            The sentence to censor.
        """
        check = await self.bot.censor_message(sentence)
        return await ctx.reply(check)
    
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
    async def mute(self, ctx: Context, member: discord.Member, *, time: UserFriendlyTime(default='...') = None) -> Optional[discord.Message]: # type: ignore
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
                    await channel.edit(overwrites=overwrites)
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
            time.dt if time else None,
            'mutes',
            precise=False,
            roles=original_roles,
            channels=channels,
            member=member.id,
            moderator=ctx.author.id,
            type='mute'
        )
        
        embed = self.bot.Embed(title='Muted', description=f'{member.mention} has been muted.')
        embed.add_field(name='Reason', value=time.arg if time else 'No reason provided.')
        embed.add_field(name='Expires', value=_format_dt(timer.expires) if timer.expires else "Does not expire.")
        embed.add_field(name='Moderator', value=ctx.author.mention)
        embed.add_field(name='Role(s) Affected', value=', '.join([f'<@&{r}>' for r in original_roles] or ['No roles.']))
        embed.add_field(name='Channel(s) Affected', value=', '.join([f'<#{c}>' for c in channels] or ['No channels.']))
        return await ctx.send(embed=embed, view=None, content=None, allowed_mentions=discord.AllowedMentions.none()) # type: ignore
                
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

        temp = timer.Timer(record=data)
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
            
        temp = timer.Timer(record=data)
        
        embed = self.bot.Embed(
            title=f'Mute info on {str(member)}',
            description=f'{member.mention} is muted! They will be unmuted at {_format_dt(temp.expires)}.'
        )
        embed.add_field(name='Created At', value=discord.utils.format_dt(temp.created_at, style='F'), inline=False)
        
        expires_fmt = f'Expires in {human_timedelta(expires)} ({_format_dt(expires)})' if (expires := temp.expires) else 'Does not expire.'
        embed.add_field(name='Expires', value=expires_fmt, inline=False)
        embed.add_field(name='Mute Reason', value=temp.kwargs.get('reason', 'None given.'), inline=False)
        embed.add_field(name='Moderator', value=f'<@{moderator}>' if (moderator := temp.kwargs.get('moderator')) else 'No moderator given.')
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
            new = timer.Timer(record=entry)
            
            fmt = f"**Reason**: {new.kwargs['reason']}\n" \
                f"**Created**: {discord.utils.format_dt(new.created_at, style='F')}\n" \
                f"**Expires**: {discord.utils.format_dt(new.expires, style='F') if new.expires else 'Never'}\n"
            
            embed.add_field(name=f'Mute {index+1}', value=fmt, inline=False)
        
        return await ctx.send(embed=embed)
    
    @commands.command(name='unmute', description='Unmute a member.')
    async def unmute(self, ctx: Context, member: discord.Member) -> None:
        await self.mute_remove(ctx, member)
        
    @commands.Cog.listener()
    async def on_mutes_timer_complete(self, timer: timer.Timer) -> None:
        """|coro|
        
        Called when an existing mute on a member is expired. This will unmute them.
        
        Parameters
        ----------
        timer: :class:`timer.Timer`
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
        
    
        
async def setup(bot):
    return await bot.add_cog(Moderation(bot))
