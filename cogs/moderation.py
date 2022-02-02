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
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands

from cogs.utils import time, timer, constants
from cogs.utils.enums import Reasons
from cogs.utils.errors import ProfanityFailure
from cogs.utils.context import Context
from cogs.utils.db import Row, Table


if TYPE_CHECKING:
    from bot import FuryBot
    
log = logging.getLogger(__name__)
    
__all__ = (
    'LockdownTable',
    'Moderation',
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
        
class LockdownHistory(Table, name='lockdown_history'):
    def __init__(self) -> None:
        super().__init__(keys=[
            Row('member', 'BIGINT'),
            Row('reason', 'TEXT'),
        ])
        
class string_to_reason:
    async def convert(self, ctx, argument):
        try:
            return Reasons.from_string(argument)
        except:
            raise commands.BadArgument(f'Invalid reason: {argument}')


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot
        
    async def cog_check(self, ctx) -> bool:
        roles = [r.id for r in ctx.author.roles]
        
        return (constants.CAPTAIN_ROLE in roles
            or constants.MOD_ROLE in roles
            or constants.COACH_ROLE in roles
            or constants.BYPASS_FURY in roles
        )
        
    @commands.group(
        name='lockdown',
        description='Lock down commands.'
    )
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
        
    @lockdown.slash(name='member',description='Lock down a member for a specific reason.')
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
        reason: string_to_reason, 
        total_time: Optional[time.UserFriendlyTime] = None 
    ) -> None:
        await ctx.defer(ephemeral=True)
        
        if total_time is None:
            await self.bot.lockdown(member, reason=reason, moderator=ctx.author.id) # type: ignore
        else:
            e = self.bot.Embed(
                title='Please Confirm',
                description=f'Do you want to lockdown {member.mention} until {discord.utils.format_dt(total_time.dt, style="F")}?'
            )
            e.set_author(name=str(member), icon_url=member.display_avatar.url)
            e.set_footer(text=f'Member ID: {member.id}') 
        
            confirmation = await ctx.get_confirmation(embed=e)
            if not confirmation:
                return
            
            await ctx.send(embed=self.bot.Embed(
                title='Working..',
                description=f'Locking down {member.mention}.'
            ), view=None)
            
            await self.bot.lockdown(member, reason=reason, time=total_time.dt, moderator=ctx.author.id) # type: ignore
        
        e = self.bot.Embed(
            title='Success',
            description=f'I have locked down {member.mention} for reason {reason}'
        )
        e.add_field(name='Note:', value='They have been given the Lockdown Role, and all their previous roles have been removed. You can do `/freedom` to unlock them.')
        return await ctx.send(embed=e)
    
    @lockdown.slash(name='freedom', description='Remove a lockdown from a member.')
    @commands.describe('member', description='The member to set free')
    @commands.describe(
        'reason', 
        description='The reason for freeing the member.',
        choices=[commands.OptionChoice(name=Reasons.type_to_string(value), value=name) for name, value in Reasons.__members__.items()]
    )
    async def freedom(self, ctx: Context, member: discord.Member, reason: string_to_reason):
        if member.id not in self.bot.lockdowns:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is not locked down.'
            ))

        await self.bot.freedom(member, reason=reason) # type: ignore
        
        return await ctx.send(embed=self.bot.Embed(
            title='Success!',
            description=f'I have freed {member.mention} from lockdown.'
        ))
        
    @lockdown.slash(name='info', description='Get information on user lockdowns.')
    @commands.describe('member', description='The member to get information on.')
    async def lockdown_info(self, ctx: Context, member: discord.Member) -> None:
        embed = self.bot.Embed(
            title=f'Lockdown information on {member}',
            description=f"Here's all the lockdown info I could find on {member.mention}.\n\n"
        )
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        async with self.bot.safe_connection() as conn:
            data = await conn.fetch('SELECT * FROM lockdowns WHERE member = $1 AND expires > CURRENT_TIMESTAMP AND expires IS NOT NULL ORDER BY expires', member.id)
            
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} has no lockdown history!'
            ))
            
        embed.add_field(name='Total Lockdowns', value=f'{len(data)} lockdowns total.', inline=False)
        
        active_lockdowns = [(e, e['expires']) for e in data if not e['dispatched']]
        
        if active_lockdowns:
            embed.add_field(name='Active Lockdowns', value=f'{len(active_lockdowns)} active lockdowns total.', inline=False)
            
            active_lockdown, expires = max(active_lockdowns, key=lambda e: e[1])
            kwargs = active_lockdown['extra']['kwargs']
            embed.add_field(name='Closest Active Lockdown', value='{0} - Created {1} - Ends {2}'.format(
                kwargs['reason'], 
                discord.utils.format_dt(active_lockdown['created'], style='F'),
                discord.utils.format_dt(expires, style='F'),
            ), inline=False)
        
        most_recent = data[0]
        kwargs = most_recent['extra']['kwargs']
        embed.add_field(name='Most Recent Lockdown', value='{0} - Created {1} - Ends {2}'.format(
            kwargs['reason'], 
            discord.utils.format_dt(most_recent['created'], style='F'),
            discord.utils.format_dt(expires, style='F') if (expires := most_recent['expires']) is not None else 'never'
        ), inline=False)
        
        first_lockdown = data[-1]
        kwargs = first_lockdown['extra']['kwargs']
        embed.add_field(name='First Lockdown', value='{0} - Created {1} - Ends {2}'.format(
            kwargs['reason'], 
            discord.utils.format_dt(first_lockdown['created'], style='F'),
            discord.utils.format_dt(expires, style='F') if (expires := first_lockdown['expires']) is not None else 'never'
        ), inline=False)
            
        return await ctx.send(embed=embed)
        
    @commands.group(name='team',description='Edit, manage, and view teams.')
    @commands.guild_only()
    async def team(self, ctx: Context) -> None:
        return
    
    @team.slash(name='create',description='Create a team.')
    @commands.describe('name', description='The name of the team to create.')
    @commands.describe('captain', description='The captain of the team.')
    @commands.describe('members', description='A list of members to add to the team (mention them).')
    async def team_create(
        self, 
        ctx: Context, 
        name: str,
        captain: discord.Role,
        members: commands.Greedy[discord.Member]
    ) -> None:
        c_name = name.capitalize()
        tc_name = name.lower().replace(' ', '-')
        vc_name = f'{name.capitalize()} Voice'
        
        embed = self.bot.Embed(
            title='Are you sure?',
            description=f'You will be creating a team named: {name}'
        )
        embed.add_field(name='Guild Actions:', value=f'**New category named**: {c_name}\n**New text channel named**: {tc_name}\n**New voice channel named**: {vc_name}')
        embed.add_field(name='Team Members', value=', '.join([m.mention for m in members]) if members else 'No members.')
        
        value = await ctx.get_confirmation(embed=embed)
        if not value:
            return
        
        overwrites = {m: discord.PermissionOverwrite(view_channel=True) for m in members}
        overwrites[ctx.guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        overwrites[captain] = discord.PermissionOverwrite(view_channel=True)
        
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
        description='Give a sub access to a channel.',
        options=[
            commands.Option(
                name='member',
                description='The member to give sub access to.',
                type=commands.OptionType.member
            ),
            commands.Option(
                name='channel',
                description='The type of channel',
                type=commands.OptionType.channel,
                channels=[
                    commands.ChannelType.text, 
                    commands.ChannelType.voice,
                    commands.ChannelType.category
                ]
            ),
            commands.Option(
                name='permission',
                description='The permission to access or deny.',
                type=commands.OptionType.boolean
            )
        ]
    )
    async def sub(
        self, 
        ctx, 
        member: discord.Member, 
        channel: discord.TextChannel, 
        permission: bool
    ) -> None:
        kwargs = {}
        if not permission:
            kwargs['overwrite'] = None
        else:
            kwargs['view_channel'] = True
        
        formatted = 'given' if permission is True else 'removed'
        await channel.set_permissions(member, reason=f'Invoked by {ctx.author}', **kwargs)
        return await ctx.send(f'I have {formatted} {member.mention} the permission to view the channel {channel.mention}')

    @commands.group(name='profanity', description='Handle the profanity filter')
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
    async def profanity_remove(self, ctx: Context, word: str) -> None:
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
    async def wordset_add(self, ctx: Context, word: str) -> None:
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
    async def wordset_contains_profanity(self, ctx: Context,  word: str) -> None:
        check = await self.bot.contains_profanity(word)
        fmt = ' not' if check is False else ''
        return await ctx.send(f"Word {word} does{fmt} contain profanity.", ephemeral=True)
    
    @profanity.slash(
        name='censor',
        description='Censor a sentence.'
    )
    @commands.describe('sentence', description='The sentence to censor.')
    async def wordset_censor(self, ctx: Context, sentence: str) -> None:
        check = await self.bot.censor_message(sentence)
        return await ctx.send(check, ephemeral=True)
    
    # Muting members
    @commands.group(name='mute', description='Mute members.')
    async def mute(self, ctx) -> None:
        return
    
    @mute.slash(name='member', description='Mute a member.')
    @commands.describe('member', description='The member to mute.')
    @commands.describe('reason', description='The reason for muting the member.')
    @commands.describe('until', description='How long to mute the member for.')
    async def mute_member(self, ctx, member: discord.Member, reason: Optional[str], until: Optional[time.UserFriendlyTime]) -> None:
        await ctx.defer(ephemeral=True)
        
        async with self.bot.safe_connection() as conn:
            data = await conn.fetchrow('SELECT * FROM mutes WHERE member = $1 AND dispatched = $2', member.id, False)
        
        if data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is already muted.',
            ))
            
        if until is not None:
            confirmation = await ctx.get_confirmation(
                f'Are you sure you want to mute {member.mention} until {until.human_readable}?', 
                allowed_mentions=discord.AllowedMentions.none()
            )
            if not confirmation:
                return
        
        original_roles = [r.id for r in member.roles]
        
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
        try:
            await member.edit(roles=[muted_role])
        except:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'I can not edit the roles on {member.mention}.'
            ))
    
        async with self.bot.safe_connection() as conn:
            if until:
                new = await self.bot.mute_timer.create_timer(
                    until.dt,
                    member.id,
                    ctx.author.id,
                    connection=conn,
                    created=ctx.created_at,
                    roles=original_roles,
                    channels=channels,
                    reason=reason
                )
            else:
                rec = await conn.execute(
                    'INSERT INTO mutes (event, extra, expires, member, created, moderator) VALUES ($1, $2::jsonb, $3, $4, $5, $6)', 
                    'mutes', {'args': [], 'kwargs': {'roles': original_roles, 'channels': channels}}, 
                    None, member.id, ctx.created_at, ctx.author.id
                )
                new = timer.Timer(record=rec)
        
        embed = self.bot.Embed(title='Muted', description=f'{member.mention} has been muted.')
        embed.add_field(name='Reason', value=reason)
        embed.add_field(name='Expires', value=discord.utils.format_dt(new.expires, style='F') if new.expires else "Does not expire.")
        embed.add_field(name='Moderator', value=ctx.author.mention)
        embed.add_field(name='Role(s) Affected', value=', '.join([f'<@&{r}>' for r in original_roles] or ['No roles.']))
        embed.add_field(name='Channel(s) Affected', value=', '.join([f'<#{c}>' for c in channels] or ['No channels.']))
        return await ctx.send(embed=embed)
                
    @mute.slash(name='remove', description='Remove a mute on a member.')
    @commands.describe('member', description='The member to remove the mute for.')
    async def mute_remove(self, ctx, member: discord.Member) -> None:
        await ctx.defer(ephemeral=True)
        
        async with self.bot.safe_connection() as conn:
            data = await conn.fetchrow('SELECT * FROM mutes WHERE member = $1 AND dispatched = $2', member.id, False)
        
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is not muted.'
            ))

        temp = timer.Timer(record=data)
        for channel_id in temp.kwargs['channels']:
            channel = self.bot.get_channel(channel_id)
            if channel is not None:
                overwrites = channel.overwrites
                overwrites[member].update(send_messages=True)
                await channel.edit(overwrites=overwrites)
        
        roles = []
        for role_id in temp.kwargs['roles']:
            role = ctx.guild.get_role(role_id)
            if role:
                roles.append(role)
        
        await member.edit(roles=roles)
        
        async with self.bot.safe_connection() as conn:
            await conn.execute('DELETE FROM mutes WHERE id = $1', temp.id)
        
        return await ctx.send(embed=self.bot.Embed(
            title='Mute removed',
            description=f'{member.mention} has been unmuted.'
        ))
    
    @mute.slash(name='current', description='Get info on a current mute.')
    @commands.describe('member', description='The member to get info on.')
    async def mute_current(self, ctx, member: discord.Member) -> None:
        await ctx.defer(ephemeral=True)
        
        async with self.bot.safe_connection() as conn:
            data = await conn.fetchrow('SELECT * FROM mutes WHERE member = $1 AND dispatched = $2', member.id, False)
            
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='Oh no!',
                description=f'{member.mention} is not muted.'
            ))
            
        temp = timer.Timer(record=data)
        embed = self.bot.Embed(
            title='Oh no!',
            description=f'{member.mention} is already muted.'
        )
        embed.add_field(name='Created At', value=discord.utils.format_dt(temp.created_at, style='F'), inline=False)
        embed.add_field(name='Expires', value=discord.utils.format_dt(expires, style='F') if (expires := temp.expires) else 'Never', inline=False)
        embed.add_field(name='Mute Reason', value=temp.kwargs['reason'], inline=False)
        embed.add_field(name='Moderator', value=f'<@{temp.kwargs["moderator"]}>')
        embed.add_field(
            name='Channel(s) Affected', 
            value=', '.join([f'<#{id}>' for id in temp.kwargs['channels']] or ['No channels affected.']), 
            inline=False
        )
        embed.add_field(
            name='Role(s) Affected', 
            value=', '.join([f'<@&{id}>' for id in temp.kwargs['roles']] or ['No roles removed.']), 
            inline=False
        )
        return await ctx.send(embed=embed)
    
    @mute.slash(name='history', description='List the mute history of a member.')
    @commands.describe('member', description='The member to get info on.')
    async def mute_history(self, ctx, member: discord.Member) -> None:
        await ctx.defer(ephemeral=True)
        
        async with self.bot.safe_connection() as conn:
            data = await conn.fetch('SELECT * FROM mutes WHERE member = $1 ORDER by created', member.id)
        
        if not data:
            return await ctx.send(embed=self.bot.Embed(
                title='No mute history!',
                description=f'{member.mention} has no mute history.'
            ))
        
        embed = self.bot.Embed(title='Mute History', description=f'{member.mention} has a mute history {len(data)} entries long.')
        for index, entry in enumerate(data):
            new = timer.Timer(record=entry)
            
            fmt = f"**Reason**: {new.kwargs['reason']}\n" \
                f"**Created**: {discord.utils.format_dt(new.created_at, style='F')}\n" \
                f"**Expires**: {discord.utils.format_dt(new.expires, style='F') if new.expires else 'Never'}\n" \
                "**Moderator**: {0}".format(f'<@{new.moderator}>')
            embed.add_field(name=f'Mute {index+1}', value=fmt, inline=False)
        
        return await ctx.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_lockdowns_timer_complete(self, timer: timer.Timer) -> None:
        await self.bot.wait_until_ready()
        
        reason = Reasons.from_string(timer.kwargs['reason'])
        
        guild = self.bot.get_guild(constants.FURY_GUILD)
        member = guild.get_member(timer.member) or await guild.fetch_member(timer.member)
        log.info(f'On lockdowns timer complete for member {member}')
        
        await self.bot.freedom(member, reason=reason)
        
    @commands.Cog.listener()
    async def on_mutes_timer_complete(self, timer: timer.Timer) -> None:
        await self.bot.wait_until_ready()
        
        guild = self.bot.get_guild(constants.FURY_GUILD)
        member = guild.get_member(timer.member) or await guild.fetch_member(timer.member)
        log.info(f'On mutes timer complete for member {member}')
        
        for channel_id in timer.kwargs['channels']:
            channel = guild.get_channel(channel_id)
            overwrites = channel.overwrites
            if overwrites.get(member):
                overwrites[member].update(send_messages=True)
                await channel.edit(overwrites=overwrites)
                
        roles = timer.kwargs['roles']
        objs = [discord.Object(id=r) for r in roles]
        await member.edit(roles=objs)
        
        
        
def setup(bot):
    return bot.add_cog(Moderation(bot))
