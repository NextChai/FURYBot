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

import asyncpg
import datetime
import asyncio
import dateparser
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from cogs.utils import time
from cogs.utils.enums import Reasons
from cogs.utils.errors import ProfanityFailure
from cogs.utils.checks import is_captain, is_mod, is_coach
from cogs.utils.context import Context
from cogs.utils.db import Row, Table


if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'LockdownTable',
    'Moderation',
    'Timer'
)

class LockdownTable(Table, name='lockdowns'):
    def __init__(self) -> None:
        super().__init__(keys=[
            Row('event', 'TEXT'),
            Row('extra', 'JSONB'),
            Row('expires', 'TIMESTAMP'),
            Row('created', 'TIMESTAMP'),
            Row('member', 'BIGINT'),
        ])
    

class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires')

    def __init__(self, *, record):
        self.id = record['id']

        extra = record['extra']
        self.args = extra.get('args', [])
        self.kwargs = extra.get('kwargs', {})
        self.event = record['event']
        self.created_at = record['created']
        self.expires = record['expires']

    @classmethod
    def temporary(cls, *, expires, created, event, args, kwargs):
        pseudo = {
            'id': None,
            'extra': { 'args': args, 'kwargs': kwargs },
            'event': event,
            'created': created,
            'expires': expires
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return time.format_relative(self.created_at)

    @property
    def author_id(self):
        if self.args:
            return int(self.args[0])
        return None

    def __repr__(self):
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot
    
    @commands.group(
        name='lockdown',
        description='Lock down commands.'
    )
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def lockdown(self) -> None:
        """A command group to interact with locking down members.
        
        Subcommands
        -----------
        member: `/lockdown member <member> <reason> <time> <datetime>`
            Lockdown a member for a reason and an optional time frame.
        freedom: `/lockdown freedom <member> <reason>`
            Free a member from lockdown and restore their permission to the server.
        """
        return
        
    @lockdown.slash(
        name='member',
        description='Lock down a member for a specific reason.'
    )
    @commands.describe('member', description='The member to lock.')
    @commands.describe(
        'reason', 
        description='The reason for locking the member.',
        choices=[commands.OptionChoice(name=Reasons.type_to_string(value), value=name) for name, value in Reasons.__members__.items()]
    )
    @commands.describe('total_time', description='A specific date you want to unlock them.')
    async def lockdown_member(
        self, 
        ctx: Context, 
        member: discord.Member, 
        reason: str, 
        total_time: Optional[time.UserFriendlyTime] = None
    ) -> None:
        freason = Reasons.from_string(reason) 
        if total_time is None:
            await self.bot.lockdown(member, reason=freason)
        else:
            e = self.bot.Embed(
                title='Please Confirm',
                description=f'Do you want to lockdown {member.mention} until {time.human_time(total_time)}?'
            )
            e.set_author(name=str(member), icon_url=member.display_avatar.url)
            e.set_footer(text=f'Member ID: {member.id}') 
        
            confirmation = await ctx.get_confirmation(embed=e)
            if not confirmation:
                return
            await self.bot.lockdown(member, reason=freason, time=total_time.dt)
        
        e = self.bot.Embed(
            title='Success',
            description=f'I have locked down {member.mention} for reason {reason}'
        )
        e.add_field(name='Note:', value='They have been given the Lockdown Role, and all their previous roles have been removed. You can do `/freedom` to unlock them.')

        return await ctx.send(embed=e)
    
    @lockdown.slash(
        name='freedom',
        description='Remove a lockdown from a member.',
        options=[
            commands.Option(
                name='member',
                description='The member to free',
                type=commands.OptionType.user,
                required=True
            ),
            commands.Option(
                name='reason',
                description='The reason for freeing the member.',
                type=commands.OptionType.string,
                choices=[commands.OptionChoice(name=Reasons.type_to_string(value), value=name) for name, value in Reasons.__members__.items()],
                required=True
            )
        ]
    )
    async def freedom(self, ctx: Context, member: discord.Member, reason: str):
        raise NotImplementedError
        
    @commands.group(
        name='team',
        description='Edit, manage, and view teams.'
    )
    @commands.check_any(is_captain(), is_coach(), is_mod())
    @commands.guild_only()
    async def team(self) -> None:
        return
    
    @team.slash(
        name='create',
        description='Create a team.',
        options=[
            commands.Option(
                name='name',
                description='The team name.',
                type=commands.OptionType.string,
                required=True
            ),
            commands.Option(
                name='captain_role',
                description='Mention the correct captain role to have access to the channel.',
                type=commands.OptionType.role,
                required=True
            )
        ] + [
            commands.Option(
                name=f'mem{index+1}', 
                description=f'Add a member.',
                type=commands.OptionType.user,
                required=True if index+1 <= 3 else False
            ) for index in range(6)
        ]
    )
    async def team_create(
        self, 
        ctx: Context, 
        name: str, 
        captain_role: discord.Role,
        *args
    ) -> None:
        members = [m for m in ctx.args if isinstance(m, discord.Member)]
        t_members = [m.mention for m in members]
        
        c_name = name.capitalize()
        tc_name = name.lower().replace(' ', '-')
        vc_name = f'{name.capitalize()} Voice'
        
        embed = self.bot.Embed(
            title='Are you sure?',
            description=f'You will be creating a team named: {name}'
        )
        embed.add_field(name='Guild Actions:', value=f'**New category named**: {c_name}\n**New text channel named**: {tc_name}\n**New voice channel named**: {vc_name}')
        embed.add_field(name='Team Members', value=', '.join(t_members) if t_members else 'No members.')
        
        value = await ctx.get_confirmation(embed=embed)
        if not value:
            return
        
        overwrites = {m: discord.PermissionOverwrite(view_channel=True) for m in members}
        overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        overwrites[captain_role] = discord.PermissionOverwrite(view_channel=True)
        
        category = await ctx.guild.create_category(c_name, overwrites=overwrites)
        text = await category.create_text_channel(c_name)
        voice = await category.create_voice_channel(vc_name)
        
        embed = self.bot.Embed(
            title='Success!',
            description=f'I have created a category named {category.mention}, a text channel called {text.mention}, and a voice channel called {voice.mention}'
        )
        return await ctx.send(embed=embed)
    
    @team.slash(
        name='is_valid',
        description='See if a Fortnite team is valid.',
        options=[
            commands.Option(
                name=f'mem{index}', 
                description=f'Add a member.',
                type=commands.OptionType.user,
                required=True
            ) for index in range(3)
        ]
    )
    async def is_valid(self, ctx, *args):
        embed = discord.Embed(title='Team Check')
        
        members = [m for m in ctx.args if isinstance(m, discord.Member)]
        for member in members:
            roles = [role.name for role in member.roles]
            if 'PC' in roles:
                embed.add_field(name=member.nick or str(member), value='Valid.')
            else:
                embed.add_field(name=member.nick or str(member), value='Not Valid.')
        
        return await ctx.send(embed=embed)
        
    @commands.slash(
        name='sub',
        description='Give a sub access to a channel.'
    )
    @commands.describe('member', description='The member to give access to.')
    @commands.describe('channel', channels=[commands.ChannelType.text, commands.ChannelType.voice])
    @commands.describe('permission', description='Whether to allow or deny access.')
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def sub(
        self, 
        ctx, 
        member: discord.Member, 
        channel: discord.TextChannel, 
        permission: bool
    ) -> None:
        value = True if permission == 'allow' else False
        kwargs = {}
        if not value:
            kwargs['overwrite'] = None
        else:
            kwargs['view_channel'] = True
        
        formatted = 'given' if value is True else 'removed'
        await channel.set_permissions(member, reason=f'Invoked by {ctx.author}', **kwargs)
        return await ctx.send(f'I have {formatted} {member.mention} the permission to view the channel {channel.mention}')

    @commands.group(name='profanity', description='Handle the profanity filter')
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def profanity(self) -> None:
        """A command group to handle and interact with the profanity filter.
        
        
        Subcommands
        -----------
        remove: `/provanity remove <word>`
            Used to remove a word from the profanity filter making it a good word.
        add: `/profanity add <word>`
            Used to add a word to the profanity filter making a good word a bad word.
        contains_profanity: `/profanity contains_profanity <word>`
            Used to determine if a word / phrase contains profanity.
        censor: `/profanity censor <word>`
            Used to censor a word or sentence.
        """
        return
    
    @profanity.slash(
        name='remove',
        description='Make a word bad word a good word'
    )
    @commands.describe('word', description='The word to remove from the profanity filter')
    async def profanity_remove(
        self, 
        ctx: Context, 
        word: str
    ) -> None:
        try:
            await self.bot.add_word_to('clean', word, wrapper=self.bot.wrap)
            return await ctx.send(f'Removed "{word}" from the list of banned words', ephemeral=True)
        except ProfanityFailure as exc:
            return await ctx.send(str(exc).capitalize(), ephemeral=True)
    
    @profanity.slash(
        name='add' ,
        description='Make a word a profanity word.'
    )
    @commands.describe('word', description='The word to add.')
    async def wordset_add(
        self, 
        ctx: Context, 
        word: str
    ) -> None:
        try:
            await self.bot.add_word_to('profanity', word, wrapper=self.bot.wrap)
            return await ctx.send(f'Added {word} to the list of banned words', ephemeral=True)
        except ProfanityFailure as exc:
            return await ctx.send(str(exc).capitalize(), ephemeral=True)
    
    @profanity.slash(
        name='contains_profanity',
        description='Determine if a word contains profanity.'
    )
    @commands.describe('word', description='The word to check for profanity.')
    async def wordset_contains_profanity(
        self, 
        ctx: Context, 
        word: str
    ) -> None:
        check = await self.bot.contains_profanity(word)
        fmt = ' not' if check is False else ''
        return await ctx.send(f"Word {word} does{fmt} contain profanity.", ephemeral=True)
    
    @profanity.slash(
        name='censor',
        description='Censor a sentence.'
    )
    @commands.describe('sentence', description='The sentence to censor.')
    async def wordset_censor(
        self, 
        ctx: Context, 
        sentence: str
    ) -> None:
        check = await self.bot.censor_message(sentence)
        return await ctx.send(check, ephemeral=True)
        
        
def setup(bot):
    return bot.add_cog(Moderation(bot))