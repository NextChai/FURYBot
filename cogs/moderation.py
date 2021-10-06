from __future__ import annotations

import discord
from discord.ext import commands

import dateparser
from typing import TYPE_CHECKING, Optional

from cogs.utils.enums import Reasons
from cogs.utils.checks import is_captain, is_mod, is_coach
from cogs.utils import time

if TYPE_CHECKING:
    from bot import FuryBot

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot: FuryBot = bot

    @commands.group(name='profanity', description='Handle the profanity filter')
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def profanity(self):
        pass
    
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
    async def profanity_remove(self, ctx, word: str) -> None:
        await self.bot.add_word_to('clean', word, wrapper=self.bot.wrap)
        return await ctx.send(f'Removed "{word}" from the list of banned words', ephemeral=True)
    
    @profanity.slash(
        name='add',
        description='Make a word a profanity word.',
        options=[
            commands.CommandOption(
                name='word',
                description='The word to add.',
                required=True
            )
        ]
    )
    async def wordset_add(self, ctx, word: str) -> None:
        await self.bot.add_word_to('profanity', word, wrapper=self.bot.wrap)
        return await ctx.send(f'Added {word} to the list of banned words', ephemeral=True)
    
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
    async def wordset_contains_profanity(self, ctx, word: str) -> None:
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
    async def wordset_censor(self, ctx, sentence: str) -> None:
        check = await self.bot.censor_message(sentence)
        return await ctx.send(check, ephemeral=True)
        
    @commands.group(
        name='lockdown',
        description='Lock down commands.'
    )
    @commands.check_any(is_captain(), is_coach(), is_mod())
    async def lockdown(self):
        pass
        
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
    async def lockdown_member(self, ctx, member: discord.Member, reason_string: str, total_seconds: Optional[str] = None, human_time: Optional[str] = None):
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
    async def freedom(self, ctx, member: discord.Member, reason: str):
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
    async def ban(self, ctx):
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
    async def kick(self, ctx):
        target = ctx.target
        if not isinstance(target, discord.Member):
            return await ctx.send("An internal error happened! Please try again later.", ephemeral=True)
        
        await target.kick(reason=f'Requested by {ctx.author} via application command.')
        
        
def setup(bot):
    bot.add_cog(Moderation(bot))