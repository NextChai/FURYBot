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
from re import L
import re

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Union,
)

import discord
from discord.ext import commands

from .teams import Team
from utils import BaseCog, Context, constants
from utils.time import td_format, UserFriendlyTime, human_timedelta
from bot import Embed

if TYPE_CHECKING:
    from bot import FuryBot

def authorized_member(ctx: Context[FuryBot]) -> bool:
    if isinstance(ctx.author, discord.User):
        raise commands.NoPrivateMessage('This command cannot be used in private messages.')
    
    authorized = (constants.CAPTAIN_ROLE, constants.MOD_ROLE, constants.COACH_ROLE, constants.BYPASS_FURY)
    result = any(r.id in authorized for r in ctx.author.roles)
    if not result:
        raise commands.MissingPermissions(['server_moderator'])
    
    return True
    
def limit_to_moderation():
    async def predicate(ctx: Context[FuryBot]) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command cannot be used in private messages.')
        
        return authorized_member(ctx)
    
    return commands.check(predicate)
    
    
class Tracking(BaseCog):
    
    async def start_tracking(self, member: discord.Member, game: Union[discord.Game, discord.Activity]) -> None:
        if member.id != 146348630926819328:
            return
        
        start = game.start
        if not start:
            start = discord.utils.utcnow()
        
        information = {
            'name': game.name,
            'type': game.type.value,
            'finished': False, # Denotes that the game_sessions list is not yet finished
        }
        session = [start,] # When the user started playing the game, which should be now
        
        async with self.bot.safe_connection() as connection:
            # Let's try and find their team
            team_data = await connection.fetchrow('SELECT * FROM teams WHERE $1 = ANY(roster) OR $1 = ANY(subs)', member.id)
            if not team_data:
                return
            
            team = Team(guild=member.guild, record=team_data)
            
            data = await connection.fetchval('SELECT * FROM tracking WHERE member = $1', member.id)
            if data: # This data has already been created, update it
                current_session_data = data['game_sessions']
                current_session_data.append(session)
                
                current_information = data['information']
                current_information.append(information)
                data = await connection.fetchrow(
                    'UPDATE tracking SET game_sessions = $1, game_information = $2 WHERE id = $3 RETURNING *', 
                    current_session_data, current_information, data['id']
                )
            else:
                await connection.execute("""
                    INSERT INTO tracking (member, team_id, game_sessions, game_information)     
                    VALUES ($1, $2, $3, $4)        
                """, member.id, team.id, [session], [information])
                
    async def close_tracking(self, member: discord.Member, game: Union[discord.Game, discord.Activity]) -> None:
        if member.id != 146348630926819328:
            return
        
        print('Ending tracking for', member)
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM tracking WHERE member = $1', member.id)
            if not data:
                return
            
            current_information = data['game_information']
            if current_information[-1]['finished']: # Something goofed here, but the data should be complete...
                return
            
            if current_information[-1]['game'] != game.name: # Something majorly goofed here!
                return
            
            current_session = data['game_sessions'][-1]
            if len(current_session) == 1: 
                current_session.append(discord.utils.utcnow()) # Append the end time
                
            # Now update our data
            current_information[-1]['finished'] = True
            await connection.execute('UPDATE tracking SET game_sessions = $1, game_information = $2 WHERE id = $3', current_session, current_information, data['id'])

        if data['notifications']:
            current = current_information[-1]
            embed = Embed(
                title='Session Finished',
                description='Your session of `{0}` has finished, here\'s the recap.'.format(current['game'])
            )
            
            total_time_played = current_session[1] - current_session[0]
            embed.add_field(name='Total Time Played', value='{} ({} - {})'.format(
                td_format(total_time_played), discord.utils.format_dt(current_session[0], style='t'), discord.utils.format_dt(current_session[1], style='t')
            ))
            await self.bot.send_to(member, embed=embed)
    
    @commands.Cog.listener('on_presence_update')
    async def on_presence_update(self, before: discord.Member, after: discord.Member) -> None:
        if not before.activities and not after.activities:
            return
        
        def _find_activity(activities) -> Optional[Union[discord.Game, discord.Activity]]:
            maybe_activity = None
            for act in activities:
                if isinstance(act, discord.Activity) and act.type is discord.ActivityType.playing:
                    maybe_activity = act
                
                if isinstance(act, discord.Game):
                    return act
            
            return maybe_activity
        
        before_game: Optional[Union[discord.Game, discord.Activity]] = _find_activity(before.activities)
        after_game: Optional[Union[discord.Game, discord.Activity]] = _find_activity(after.activities)
        
        if not before_game and not after_game:
            return
        elif before_game and after_game: # Wait what this cant happen but in case it does...
            return
        
        if before_game and not after_game: # User stopped playing the game
            await self.close_tracking(after, before_game)
        if after_game and not before_game: # User started playing the game
            await self.start_tracking(after, after_game)
        
    @commands.group(name='tracking', aliases=['track'], description='Toggle game tracking.', invoke_without_command=True)
    async def tracking(self, ctx: Context[FuryBot]) -> None:
        return
    
    @tracking.command(name='notis', aliases=['notifications', 'verbose'], description='Toggle game tracking notifications.')
    async def tracking_notis(Self, ctx: Context[FuryBot], on_off: bool) -> None:
        """|coro|
        
        Turn on or off game time tracking notifications. `Off` means you will not be notified of game sessions,
        and `On` means you will be notified of game sessions.
        
        Parameters
        ----------
        on_off: :class:`bool`
            Whether to turn on or off game tracking notifications.
        """
        ...
    
    # Now for moderation commands:
    @tracking.command(name='stats', description='Get tracking stats on a specific member.', aliases=['stat'])
    async def tracking_stats(self, ctx: Context[FuryBot], member: Optional[discord.Member], *, time: UserFriendlyTime(force_future=False) = None) -> Optional[discord.Message]: # type: ignore
        if member and not authorized_member(ctx):
            return await ctx.send('You can not use this command on other members.')
    
        target = member or ctx.author
        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow('SELECT * FROM tracking WHERE member = $1', target.id)
        
        if not data:
            return await ctx.send(f'{target.mention} does not have a game tracking history')
        
        # Let's sort our data then create our embed
        sorted_data: Mapping[str, Dict[str, Any]] = {}
        
        # {
        #     'Rocket League': {
        #         'history': [
        #             [datetime.datetime, datetime.datetime]
        #         ],
        #         'times': 1,
        #         'total': datetime.timedelta
        #     }
        # }
        
        for index, entry in enumerate(data['game_sessions']):
            entry_information = data['game_information'][index]
            if not entry_information['finished']:
                continue
            
            name = entry_information['name']
            if name not in sorted_data:
                sorted_data[name] = {
                    'history': [entry]
                }
            
        for key, value in sorted_data.items():
            history = value['history']
            sorted_data[key]['times'] = len(history)
            
            # Now let's get total delta
            times = []
            for entry in history:
                if (time and time.dt > ctx.message.created_at and entry[1] > time.dt) or not time:
                    times.append(entry[1] - entry[0])
                    
            
            sorted_data[key]['total'] = sum(times)
        
        embed = Embed(
            title=f'{target.display_name}\'s Game Tracking History',
            description=f'{target.mention} has played {len(sorted_data)} games total{0}.'.format(
                f' in the span of {human_timedelta(time.dt)}' if time else ''
            )
        )
        for game, packet in sorted_data.items():
            fmt = {
                'Times Played': packet['times'],
                'Total Time Played': td_format(packet['total'])
            }
            embed.add_field(name=game, value='\n'.join(f'**{key}**: {value}' for key, value in fmt.items()))
            
        return await ctx.send(embed=embed)
    
    
async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Tracking(bot))