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
import functools

import logging
from typing import TYPE_CHECKING, Tuple, List

import discord
from discord import app_commands
from discord.ext import commands

from utils import BaseCog, human_join, human_timestamp, SelectOneOfMany, BaseView
from .persistent.sub_finding import SubFinder
from .gameday import GamedayImage

if TYPE_CHECKING:
    from bot import FuryBot
    from .gameday import Gameday

__all__: Tuple[str, ...] = ('GamedayEventListener', 'GamedayCommands')

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)


class SelectAGameday(BaseView):
    @property
    def embed(self) -> discord.Embed:
        return self.bot.Embed(
            title='Multiple Gamedays',
            description='There is more than one gameday going on at the moment, please use '
            'the select below to choose which you would like to add an image for.',
        )


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

        if not gameday.voting.has_votes_needed:
            return

        view = self.bot.score_report_view
        if view is None:
            _log.debug('Score report view not found.')
            return

        # Let's create the embed and send it to the channel
        embed, attachments = await view.create_sender_information(gameday)
        message = await team.text_channel.send(
            embed=embed,
            view=view,
            files=attachments,
        )

        await message.reply(
            content=human_join(
                (m.mention for m in gameday.attending_members),
                additional='your gameday has started! This message will automatically delete in 60 seconds.',
            ),
            allowed_mentions=discord.AllowedMentions(users=True),
            delete_after=60,
        )

        async with self.bot.safe_connection() as connection:
            await gameday.edit(
                connection=connection,
                score_message_id=message.id,
            )

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

        captain_mentions = (c.mention for c in team.captain_roles)
        captain_mention_content = (
            human_join(captain_mentions, additional='please note the following:') if captain_mentions else None
        )

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
                content=captain_mention_content,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            return

        # We do not have enough votes, so we need to check for automatic sub finding and act accordingly.
        sub_finding = await gameday.getch_sub_finding()
        if sub_finding.enabled:
            try:
                await SubFinder.create(gameday=gameday, now=discord.utils.utcnow())
            except ValueError as exc:
                embed = self.bot.Embed(title='Error With Automatic Sub Finding', description=f'Error: {exc}')
                await team.text_channel.send(
                    embed=embed,
                    content=human_join((obj.mention for obj in [*team.captain_roles, *gameday.attending_members])),
                )

            return

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
            content=captain_mention_content,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    @commands.Cog.listener('on_sub_finding_end_timer_complete')
    async def on_sub_finding_end(self, *, guild_id: int, team_id: int, gameday_id: int) -> None:
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

        sub_finding = await gameday.getch_sub_finding()

        message = await sub_finding.fetch_message()
        if message is not None:
            await message.edit(view=None)

        update_message = await sub_finding.fetch_update_message()

        if gameday.voting.has_votes_needed:
            # We can update the status message to let them know that we have enough votes now.
            embed = self.bot.Embed(
                title='Substitutes Found',
                description='Enough substitutes have been found to fill the team for the upcoming gameday. The '
                f'gameday will start at {human_timestamp(gameday.starts_at)} without issues.',
            )

            embed.add_field(
                name='Subs Found', value=human_join((m.mention for m in gameday.attending_members if m.is_temporary_sub))
            )
            if update_message is not None:
                await update_message.reply(embed=embed)

        # We need to yell at them and let them know we could not get enough members.
        embed = team.embed(
            title='Unable To Locate Substitutes',
            description='This gameday will not start as it does not have the minimum amount of '
            f'players required to start. This gameday is missing **{bucket.per_team - len(gameday.attending_members)} votes**.',
        )
        embed.add_field(
            name='Attending Members', value=human_join((m.mention for m in gameday.attending_members)), inline=False
        )
        embed.add_field(
            name='Not Attending Members', value=human_join((m.mention for m in gameday.not_attending_members)), inline=False
        )
        embed.add_field(
            name='Automatic Sub Finding Ended',
            value='Automatic sub finding has ended, but there is still hope. If a substitute is found, '
            'they can be added to the team and the gameday will start as normal.',
            inline=False,
        )

        if update_message is not None:
            await update_message.reply(embed=embed)


class GamedayCommands(BaseCog):
    gameday = app_commands.Group(name='gameday', description='Commands related to gamedays.', guild_only=True)

    async def _add_image(
        self, interaction: discord.Interaction, gameday: Gameday, image: discord.Attachment
    ) -> discord.InteractionMessage:
        async with self.bot.safe_connection() as connection:
            gameday_image = await GamedayImage.create(
                self.bot,
                connection=connection,
                guild_id=gameday.guild_id,
                team_id=gameday.team_id,
                gameday_id=gameday.id,
                bucket_id=gameday.bucket_id,
                url=image.url,
                uploader_id=interaction.user.id,
                uploaded_at=interaction.created_at,
            )

        gameday.add_image(gameday_image)

        message = await gameday.fetch_score_message()
        if message is not None and self.bot.score_report_view:
            embed, attachments = await self.bot.score_report_view.create_sender_information(gameday)
            await message.edit(embed=embed, attachments=attachments)

        return await interaction.edit_original_response(content='Image uploaded successfully.')

    async def _select_gameday_after(
        self,
        interaction: discord.Interaction[FuryBot],
        values: List[str],
        *,
        gamedays: List[Gameday],
        image: discord.Attachment,
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        value = values[0]
        gameday = discord.utils.get(gamedays, id=int(value))
        assert gameday

        return await self._add_image(interaction, gameday, image)

    @gameday.command(name='upload')
    async def gameday_upload(
        self, interaction: discord.Interaction[FuryBot], image: discord.Attachment
    ) -> discord.InteractionMessage:
        assert interaction.guild
        assert interaction.channel_id

        await interaction.response.defer(ephemeral=True)

        # Let's try and find the gameday that this image is for.. first let's find the team.
        team = self.bot.get_team_from_channel(interaction.channel_id, interaction.guild.id)
        if team is None:
            return await interaction.edit_original_response(content="You must invoke this command in a team channel.")

        gamedays = team.ongoing_gamedays
        if len(gamedays) > 1:
            # We need to have the user select one..
            view = SelectAGameday(target=interaction)
            SelectOneOfMany(
                view,
                options=[
                    discord.SelectOption(label=gameday.starts_at.strftime("%I:%M %p"), value=str(gameday.id))
                    for gameday in gamedays
                ],
                after=functools.partial(self._select_gameday_after, gamedays=gamedays, image=image),
                placeholder='Select a gameday...',
            )

        gameday = gamedays[0]
        return await self._add_image(interaction, gameday, image)
