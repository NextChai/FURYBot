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

import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import discord

from utils import human_timedelta

if TYPE_CHECKING:
    import asyncpg

    from bot import FuryBot
    from ..team import Team

__all__: Tuple[str, ...] = ('PracticeStatus', 'AttendingMember', 'Practice')


class PracticeStatus(Enum):
    ongoing = 'ongoing'
    completed = 'completed'


class AttendingMember:
    def __init__(self, *, practice: Practice, data: Dict[Any, Any]) -> None:
        self.practice: Practice = practice

        self.member_id: int = data['member_id']
        self.joined_at: datetime.datetime = data['joined_at']
        self.left_at: Optional[datetime.datetime] = data['left_at']

    @property
    def mention(self) -> str:
        return f'<@{self.member_id}>'


class Practice:
    def __init__(self, *, bot: FuryBot, team: Team, data: Dict[Any, Any], attending: List[Dict[Any, Any]]) -> None:
        self.bot: FuryBot = bot

        self.team: Team = team

        self.id: int = data['id']
        self.guild_id: int = data['guild_id']
        self.status: PracticeStatus = PracticeStatus(data['status'])
        self.initiated_by_id: int = data['initiated_by_id']
        self.message_id: int = data['message_id']
        self.attending_members: Dict[int, AttendingMember] = {
            entry['member_id']: AttendingMember(practice=self, data=entry) for entry in attending
        }
        self.initiated_at: datetime.datetime = data['initiated_at']
        self.ended_at: Optional[datetime.datetime] = data['ended_at']

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=f'{self.team.display_name} Practice.',
            description='Team practices are mandatory once a week for all members on the team. This practice was '
            f'initiated by <@{self.initiated_by_id}> on {discord.utils.format_dt(self.initiated_at, "F")} '
            f'({discord.utils.format_dt(self.initiated_at, "R")}).',
        )
        embed.set_thumbnail(url=self.team.logo)

        embed.add_field(
            name='Attending Members',
            value=', '.join(member.mention for member in self.attending_members.values()),
            inline=False,
        )

        # Let's also add a field to members who've attended but aren't currently in the voice channel.
        voice_channel_member_ids = [member.id for member in self.team.voice_channel.members]
        left_members = [
            member for member in self.attending_members.values() if member.member_id not in voice_channel_member_ids
        ]
        if left_members:
            # Let's get a delta of how long they've been in the voice channel.
            formatted = [
                f'{member.mention}: Attended for {human_timedelta((member.left_at - member.joined_at).total_seconds())}'
                for member in left_members
                if member.left_at
            ]

            embed.add_field(
                name='Members Who\'ve Left The Voice Practice:',
                value='\n'.join(formatted),
                inline=False,
            )

        embed.add_field(
            name='How Do I Attend?',
            value='**To attend your team practice, simply press the "Attending" button below while in your '
            'team\'s voice channel. Optionally, you can join your team\'s voice channel instead. '
            'Your team practice time will be recorded once you leave the voice channel.**',
            inline=False,
        )

        embed.add_field(
            name='I Can\'t Attend!',
            value='Contact your team captain and let them know you can\'t attend this practice. They will '
            'make an exception for you.',
        )

        return embed

    @property
    def ongoing(self) -> bool:
        return self.status is PracticeStatus.ongoing

    async def handle_attending_member_join(self, member: discord.Member, joined_at: datetime.datetime) -> None:
        data = await self.bot.pool.fetchrow(
            'INSERT INTO teams.practice_attending(practice_id, member_id, joined_at) VALUES($1, $2, $3) RETURNING *',
            self.id,
            member.id,
            joined_at,
        )
        assert data

        attending_member = AttendingMember(practice=self, data=dict(data))
        self.attending_members[attending_member.member_id] = attending_member

    async def handle_practice_end(self, ended_at: datetime.datetime, connection: asyncpg.Connection[asyncpg.Record]) -> None:
        # It's safe to say that if this practice lasted under 10 minutes it's not worth recording. This means we'll just
        # delete it from the database and not track it for logs.
        total_time_today = ended_at - self.initiated_at
        if total_time_today < datetime.timedelta(minutes=10):
            await connection.execute(
                'DELETE FROM teams.practice WHERE id = $1',
                self.id,
            )
            # and remove it from the bot's cache
            self.bot.team_practice_cache.pop(self.id, None)

            message = await self.team.text_channel.fetch_message(self.message_id)
            await message.edit(
                view=None,
                embed=self.bot.Embed(
                    title="Invalid Practice Not Recorded",
                    description="This practice was too short to be recorded. Practices need to be at "
                    "least 10 minutes long.",
                ),
            )

            return

        # Let's update the team practice status to be completed.
        self.ended_at = ended_at
        self.status = PracticeStatus.completed
        await self.bot.pool.execute(
            'UPDATE teams.practice SET status = $1 WHERE id = $2',
            PracticeStatus.completed.value,
            self.id,
        )

        # Awesome, now we can edit the persistent view and remove the attending button.
        # Let's also ping the team captains and let them know this practice has been completed.
        # We forced the command to be invoked in the team's voice channel, so we can make
        # an assumption here.
        message = await self.team.text_channel.fetch_message(self.message_id)
        await message.edit(view=None)

        # Let's show some neat stats about the practice and ping the captain about it.
        practice_history = self.team.practices

        embed = self.bot.Embed(
            title=f'{self.team.display_name} Practice Completed.',
            description=f'This team practice initiated by <@{self.initiated_by_id}> on '
            f'{discord.utils.format_dt(self.initiated_at, "F")} ({discord.utils.format_dt(self.initiated_at, "R")}) '
            'has been completed. Here are some stats:',
        )
        embed.set_thumbnail(url=self.team.logo)

        stats: List[str] = []

        stats.append(f"**This session**: {human_timedelta(total_time_today.total_seconds())}")

        # Let's get the weekly time and total time.
        weekly_time = 0
        total_time = 0
        for l_practice in practice_history:
            l_initiated_at = l_practice.initiated_at
            l_ended_at = l_practice.ended_at

            if l_initiated_at and l_ended_at:
                practice_time = (l_ended_at - l_initiated_at).total_seconds()
                total_time += practice_time

                # Let's check if this practice was within the last 7 days.
                if (discord.utils.utcnow() - l_initiated_at).days <= 7:
                    weekly_time += practice_time

        stats.append(f"**Weekly Time**: {human_timedelta(weekly_time)}")
        stats.append(f"**Total Time**: {human_timedelta(total_time)}")

        embed.add_field(name="Time Spent Practicing:", value='\n'.join(stats), inline=False)

        # Let's compare this team's total practice time to other teams and get a rank for them.
        rank = await self.team.fetch_practice_rank(connection=connection)

        embed.add_field(
            name='Practice Time Rank',
            value=f'Out of all the other teams, this team is ranked **#{rank}** out of **{len(self.bot.team_cache)}** teams '
            'for total practice time.',
            inline=False,
        )

        # Let's get the average time spent practicing per day.
        average_time = total_time / (total_time_today.total_seconds() / 86400)
        embed.add_field(
            name='Average Time Spent Practicing Per Day',
            value=f'This team has spent an average of **{human_timedelta(average_time)}** per day practicing.',
            inline=False,
        )

        await message.reply(
            embed=embed,
            content=", ".join(captain.mention for captain in self.team.captain_roles),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    async def handle_attending_member_leave(self, member: discord.Member, left_at: datetime.datetime) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.practice_attending SET left_at = $1 WHERE practice_id = $2 AND member_id = $3',
                left_at,
                self.id,
                member.id,
            )

            self.attending_members[member.id].left_at = left_at

            if not all(member.left_at is not None for member in self.attending_members.values()):
                # There are still members here, we have nothing else to do.
                return

            # If all the members have left, we can mark the practice as completed.
            await self.handle_practice_end(left_at, connection)
