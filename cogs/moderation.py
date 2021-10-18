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

import dateparser
from typing import TYPE_CHECKING, Optional
import datetime

import discord
from discord.ext import commands

from cogs.utils import time
from cogs.utils.enums import Reasons
from cogs.utils.errors import ProfanityFailure
from cogs.utils.checks import is_captain, is_mod, is_coach
from cogs.utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'Moderation',
)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot
        
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
            commands.CommandOption(
                name='name',
                description='The team name.',
                type=commands.OptionType.string,
                required=True
            ),
            commands.CommandOption(
                name='captain_role',
                description='Mention the correct captain role to have access to the channel.',
                type=commands.OptionType.role,
                required=True
            )
        ] + [
            commands.CommandOption(
                name=f'mem{index}', 
                description=f'Add a member.',
                type=commands.OptionType.user,
                required=False
            ) for index in range(7)
        ]
    )
    async def team_create(
        self, 
        ctx: Context, 
        name: str, 
        captain_role: discord.Role,
        mem1: discord.Member, 
        mem2: discord.Member,
        mem3: discord.Member,
        mem4: Optional[discord.Member],
        mem5: Optional[discord.Member],
        mem6: Optional[discord.Member],
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
        
        category = await ctx.guild.create_category(c_name, overwrites=overwrites)
        text = await category.create_text_channel(c_name)
        voice = await category.create_voice_channel(vc_name)
        
        embed = self.bot.Embed(
            title='Success!',
            description=f'I have created a category named {category.mentio}, a text channel called {text.mention}, and a voice channel called {voice.mention}'
        )
        return await ctx.send(embed=embed)
    
    @team.slash(
        name='is_valid',
        description='See if a Fortnite team is valid.',
        options=[
            commands.CommandOption(
                name=f'mem{index}', 
                description=f'Add a member.',
                type=commands.OptionType.user,
                required=True
            ) for index in range(3)
        ]
    )
    async def is_valid(self, ctx, mem1, mem2, mem3):
        embed = discord.Embed(
            title='Team Check',
        )
        members = [m for m in ctx.args if isinstance(m, discord.Member)]
        for member in members:
            roles = [role.name for role in member.roles]
            if 'PC' in roles:
                embed.add_field(name=member, value='Valid.')
            else:
                embed.add_field(name=member, value='Not Valid.')
        
        return await ctx.send(embed=embed)
        
        
    @commands.slash(
        name='sub',
        description='Give a sub access to a channel.',
        options=[
            commands.CommandOption(
                name='member',
                description='The member to give access to.',
                type=commands.OptionType.user,
                required=True
            ),
            commands.CommandOption(
                name='channel',
                description='The channel to give access to.',
                type=commands.OptionType.channel,
                required=True
            ),
            commands.CommandOption(
                name='permission',
                description='Whether to deny or allow the permission',
                choices=[
                    commands.CommandOptionChoice(name='Allow Access', value='allow'),
                    commands.CommandOptionChoice(name='Deny Access', value='deny')
                ],
                required=True
            )
        ]
    )
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def sub(self, ctx, member: discord.Member, channel: discord.GuildChannel, permission: str) -> None:
        value = True if permission == 'allow' else False
        kwargs = {}
        if not value:
            kwargs['overwrite'] = None
        else:
            kwargs['view_channel'] = True
        
        formatted = 'given' if value is True else 'removed'
        await channel.set_permissions(member, reason=f'Invoked by {ctx.author}', **kwargs)
        return await ctx.send(f'I have {formatted} {member.mention} to view the channel {channel.mention}')

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
        description='Make a word bad word a good word',
        options=[
            commands.CommandOption(
                name='word',
                description='The word to remove.',
                required=True
            )
        ]
    )
    async def profanity_remove(self, ctx: Context, word: str) -> None:
        try:
            await self.bot.add_word_to('clean', word, wrapper=self.bot.wrap)
            return await ctx.send(f'Removed "{word}" from the list of banned words', ephemeral=True)
        except ProfanityFailure as exc:
            return await ctx.send(str(exc).capitalize(), ephemeral=True)
    
    @profanity.slash(
        name='add' ,
        description='Make a word a profanity word.',
        options=[
            commands.CommandOption(
                name='word',
                description='The word to add.',
                required=True
            )
        ]
    )
    async def wordset_add(self, ctx: Context, word: str) -> None:
        try:
            await self.bot.add_word_to('profanity', word, wrapper=self.bot.wrap)
            return await ctx.send(f'Added {word} to the list of banned words', ephemeral=True)
        except ProfanityFailure as exc:
            return await ctx.send(str(exc).capitalize(), ephemeral=True)
    
    @profanity.slash(
        name='contains_profanity',
        description='Determine if a word contains profanity.',
        options=[
            commands.CommandOption(
                name='word',
                description='The word to check.',
                required=True
            )
        ]
    )
    async def wordset_contains_profanity(self, ctx: Context, word: str) -> None:
        check = await self.bot.contains_profanity(word)
        fmt = ' not' if check is False else ''
        return await ctx.send(f"Word {word} does{fmt} contain profanity.", ephemeral=True)
    
    @profanity.slash(
        name='censor',
        description='Censor a sentence.',
        options=[
            commands.CommandOption(
                name='sentence',
                description='The sentence to censor.',
                required=True
            )
        ]
    )
    async def wordset_censor(self, ctx: Context, sentence: str) -> None:
        check = await self.bot.censor_message(sentence)
        return await ctx.send(check, ephemeral=True)
        
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
        description='Lock down a member for a specific reason.',
        options=[
            commands.CommandOption(
                name='member',
                description='The member to lock down.',
                type=commands.OptionType.user,
                required=True
            ),
            commands.CommandOption(
                name='reason',
                description='The reason for locking down the member.',
                type=commands.OptionType.string,
                choices=[commands.CommandOptionChoice(name=Reasons.type_to_string(value), value=name) for name, value in Reasons.__members__.items()],
                required=True
            ),
            commands.CommandOption(
                name='time',
                description='How long you want them locked.',
                type=commands.OptionType.string,
                required=False,
                choices=[
                    commands.CommandOptionChoice(name='1m', value='60'),
                    commands.CommandOptionChoice(name='1h', value='3600'),
                    commands.CommandOptionChoice(name='1d', value='86400'),
                    commands.CommandOptionChoice(name='2d', value='172800'),
                    commands.CommandOptionChoice(name='7d', value='604800'),
                ]
            ),
            commands.CommandOption(
                name='datetime', 
                description='A specific date you want to unlock them.',
                type=commands.OptionType.string,
                required=False)
        ]
    )
    async def lockdown_member(self, ctx: Context, member: discord.Member, reason_string: str, total_seconds: Optional[str] = None, human_time: Optional[str] = None):
        if total_seconds and human_time:
            return await ctx.send("You can not do both total_seconds and datetime, you need to pick one.")
        
        reason = Reasons.from_string(reason_string)
        if total_seconds is not None:
            self.bot.loop.create_task(self.bot.lockdown_for(int(total_seconds), member=member, reason=reason))
        elif human_time is not None:
            try:
                date = dateparser.parse(human_time, languages=['en'], settings={'TIMEZONE': 'UTC', 'TO_TIMEZONE': 'UTC'})
            except Exception:
                return await ctx.send("Invalid date given!")
            else:
                if date is None:
                    return await ctx.send("Invalid date given!")
            
            e = self.bot.Embed(
                title='Please Confirm',
                description=f'Do you want to lockdown {member.mention} until {time.human_time(date)}?'
            )
            confirmation = await ctx.get_confirmation(embed=e)
            if not confirmation:
                return
            
            self.bot.loop.create_task(self.bot.lockdown_until(date, member=member, reason=reason))
        else:
            self.bot.loop.create_task(self.bot.lockdown(member, reason=reason))

        total_time = total_seconds
        if human_time:
            now = datetime.datetime.utcnow()
            form = (now - date) if now > date else (date - now) # type: ignore
            total_time = form.total_seconds()
            
        
        e = self.bot.Embed(
            title='Success',
            description=f'I have locked down {member.mention} for reason {reason}'
        )
        e.add_field(name='Note:', value='They have been given the Lockdown Role, and all their previous roles have been removed. You can do `/freedom` to unlock them.')
        
        if total_time is not None:
            delta = datetime.timedelta(seconds=float(total_time))
            e.description += f', for a total of **{total_time} seconds**.. or until **{time.human_time(delta)}**'
            
        return await ctx.send(embed=e)
    
    @lockdown.slash(
        name='freedom',
        description='Remove a lockdown from a member.',
        options=[
            commands.CommandOption(
                name='member',
                description='The member to free',
                type=commands.OptionType.user,
                required=True
            ),
            commands.CommandOption(
                name='reason',
                description='The reason for freeing the member.',
                type=commands.OptionType.string,
                choices=[commands.CommandOptionChoice(name=Reasons.type_to_string(value), value=name) for name, value in Reasons.__members__.items()],
                required=True
            )
        ]
    )
    async def freedom(self, ctx: Context, member: discord.Member, reason: str):
        success = await self.bot.freedom(member, reason=Reasons.from_string(reason))
        
        fmt = "able" if success is True else "unable"
        e = self.bot.Embed(
            title='Success',
            description=f'I have removed the reason {reason} from {member.mention}s lockdown. I was {fmt} to unlock them.'
        )
        
        profile = self.bot.get_lockdown_info(member)
        if profile is not None:
            formatted = ', '.join([f'**{entry}**' for entry in profile['reasons']])
            e.add_field(name='Remaining Lockdown Reasons:', value=formatted)
        
        return await ctx.send(embed=e, ephemeral=True)
    
    @commands.slash(
        name='ban',
        description='Ban a member',
        type=commands.InteractionType.user,
    )
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: Context):
        target = ctx.target
        if not isinstance(target, discord.Member):
            return await ctx.send("An internal error happened! Please try again later.", ephemeral=True)
        
        await target.ban(reason=f'Requested by {ctx.author} via application command.')
        
    @commands.slash(
        name='kick',
        description='Kick a member',
        type=commands.InteractionType.user
    )
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: Context):
        target = ctx.target
        if not isinstance(target, discord.Member):
            return await ctx.send("An internal error happened! Please try again later.", ephemeral=True)
        
        await target.kick(reason=f'Requested by {ctx.author} via application command.')
        
        
def setup(bot):
    bot.add_cog(Moderation(bot))