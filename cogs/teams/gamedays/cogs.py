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
from typing import TYPE_CHECKING, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, human_join

if TYPE_CHECKING:
    from bot import FuryBot

__all__: Tuple[str, ...] = ('GamedayEventListener', 'GamedayCommands')

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class GamedayEventListener(BaseCog):
    @commands.Cog.listener('on_gameday_start_timer_complete')
    async def on_gameday_start(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        _log.debug('Gameday start event triggered for guild %s, team %s, gameday %s.', guild_id, team_id, gameday_id)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            _log.debug('Guild %s not found.', guild_id)
            return

        team = self.bot.get_team(team_id, guild_id=guild_id)
        if team is None:
            _log.debug('Team %s not found.', team_id)
            return

        bucket = team.get_gameday_bucket()
        if bucket is None:
            _log.debug('Gameday bucket not found.')
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug('Gameday %s not found.', gameday_id)
            return

        view = self.bot.score_report_view
        if view is None:
            _log.debug('Score report view not found.')
            return

        # Let's create the embed and send it to the channel
        embed, attachments = await view.create_sender_information(gameday)

    @commands.Cog.listener('on_gameday_voting_start_timer_complete')
    async def on_gameday_voting_start(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            _log.debug('Guild %s not found.', guild_id)
            return

        team = self.bot.get_team(team_id, guild_id=guild_id)
        if team is None:
            _log.debug('Team %s not found.', team_id)
            return

        bucket = team.get_gameday_bucket()
        if bucket is None:
            _log.debug('Gameday bucket not found.')
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug('Gameday %s not found.', gameday_id)
            return

        # We need to send the view to the channel!
        view = self.bot.attendance_voting_view
        if view is None:
            _log.debug('Attendance voting view not found.')
            return

        embed = view.create_embed(gameday)
        channel = team.text_channel

        team_member_mentions = human_join(
            (m.mention for m in team.main_roster), additional='please confirm your attendance for the upcoming gameday.'
        )

        message = await channel.send(
            embed=embed, view=view, content=team_member_mentions, allowed_mentions=discord.AllowedMentions(users=True)
        )

        async with self.bot.safe_connection() as connection:
            await gameday.edit(
                connection=connection,
                voting_message_id=message.id,
            )

    @commands.Cog.listener('on_gameday_voting_end_timer_complete')
    async def on_gameday_voting_end(self, guild_id: int, team_id: int, gameday_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            _log.debug('Guild %s not found.', guild_id)
            return

        team = self.bot.get_team(team_id, guild_id=guild_id)
        if team is None:
            _log.debug('Team %s not found.', team_id)
            return

        bucket = team.get_gameday_bucket()
        if bucket is None:
            _log.debug('Gameday bucket not found.')
            return

        gameday = bucket.get_gameday(gameday_id)
        if gameday is None:
            _log.debug('Gameday %s not found.', gameday_id)
            return

        # Let's try and fetch the message that we sent, then edit it with an updated embed
        try:
            message = await gameday.voting.fetch_message()
        except discord.NotFound:
            _log.debug('Voting message not found.')
            return
        else:
            if message is None:
                _log.debug('Voting message not found, message ID is none.')
                return

        await message.edit(view=None)

        captain_mentions = (c.mention for c in team.captain_roles)

        # Now we need to do one of X things:
        # 1. If the voting has ended and the team is filled, send an embed to the team channel
        # 2. If the voting has ended and the team is not filled, do one of two things:
        # a. If automatic sub finding is enabled, send an embed to the team channel letting them know that automatic sub findign is in progress...
        # b. If automatic sub finding is disabled, send an embed to the team channel letting them know that they need to find a sub manually.

        if gameday.voting.has_votes_needed:
            view = self.bot.attendance_voting_view
            if view is None:
                _log.debug('Attendance voting view not found.')
                return

            embed = view.create_voting_done_embed(gameday)
            await message.reply(
                embed=embed,
                content=human_join(captain_mentions, additional='please note the following:'),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            return

        # We do not have enough votes, so we need to check for automatic sub finding and act accordingly.
        if gameday.automatic_sub_finding:
            raise NotImplementedError('Can not launch automatic sub finding yet.')
        else:
            # We cannot do automatic sub finding, let's figure out why first. This cna be for one of two reasons:
            # 1. The bucket has it disabled
            # 2. The bot disabled it for this gameday due to time constraints
            if bucket.automatic_sub_finding_if_possible:
                reason = 'Due to time constraints, automatic sub finding was disabled for this gameday.'
            else:
                reason = 'Automatic sub finding is disabled for this team\'s gameday bucket.'

            embed = discord.Embed(
                title='Gameday Attendance Voting Ended',
                description='Unfortunately, we do not have enough votes to fill the team for this gameday. The miniumum '
                f'is **{bucket.per_team} players** and we only have **{len(gameday.attending_members)}** members.',
            )

            embed.add_field(
                name='Attending Members', value=human_join((m.mention for m in gameday.attending_members)), inline=False
            )
            embed.add_field(
                name='Not Atending Members',
                value='\n'.join(f'{m.mention}: {m.reason}' for m in gameday.not_attending_members),
                inline=False,
            )

            embed.add_field(name='Automatic Sub Finding Disabled', value=reason)

            await message.reply(
                embed=embed,
                content=human_join(captain_mentions, additional='please note the following:'),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )


class GamedayCommands(BaseCog):

    gameday = app_commands.Group(name='gameday', description='Commands related to gamedays.')

    @gameday.command(name='upload')
    async def gameday_upload(self, interaction: discord.Interaction[FuryBot], image: discord.Attachment) -> None:
        raise NotImplementedError('Gameday upload not implemented yet.')
