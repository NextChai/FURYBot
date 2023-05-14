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
from typing import TYPE_CHECKING, Type, NamedTuple

import discord
from typing_extensions import Self, Unpack

from utils import BaseView, BaseViewKwargs, default_button_doc_string, human_join, human_timestamp

from ...errors import TeamDeleted

if TYPE_CHECKING:
    from bot import FuryBot

    from ...team import Team
    from ..gameday import Gameday, GamedaySubFinding

SubFindingTimes = NamedTuple(
    'SubFindingTimes', [('start', datetime.datetime), ('end', datetime.datetime), ('can_use_automatic_sub_finding', bool)]
)


def determine_comfy_sub_finding_times(*, starts_at: datetime.datetime, now: datetime.datetime) -> SubFindingTimes:
    time_until_gameday_starts = starts_at - now

    if time_until_gameday_starts < datetime.timedelta(hours=1):
        # We know the moderator did something bad here, so return a sub finding time that shows
        # the sub finder can not be used.
        return SubFindingTimes(start=now, end=now, can_use_automatic_sub_finding=False)

    thirty_mins_before_starts_at = starts_at - datetime.timedelta(minutes=30)
    return SubFindingTimes(start=now, end=thirty_mins_before_starts_at, can_use_automatic_sub_finding=True)


def create_sub_finding_status_embed(gameday: Gameday) -> discord.Embed:
    team = gameday.team
    if team is None:
        raise TeamDeleted(team_id=gameday.team_id)

    embed = team.embed(
        title='Automatic Sub Finding',
        description='Below shows the current status of the automatic sub finding for this team.',
    )

    temporary_subs = [member for member in gameday.get_members() if member.is_temporary_sub]

    embed.add_field(
        name='Subs Found',
        value=human_join((m.mention for m in temporary_subs))
        if temporary_subs
        else "No temporary subs have been found yet.",
    )

    # TODO: Add more here

    return embed


class ConfirmSubFinding(BaseView):
    def __init__(self, gameday: Gameday, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)

        self.bot: FuryBot = gameday.bot
        self.gameday: Gameday = gameday

        team = gameday.team
        if team is None:
            raise TeamDeleted(team_id=gameday.team_id)

        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        embed = self.team.embed(
            title='Please Confirm',
            description='Confirm your attendance for the upcoming gameday. If you press "Confirm" you agree to show '
            'up to the gameday at the attended time and communicate with your team accoridngly. If for some reason '
            'you are unable to attend after confirming, please contact your team captain or a staff member.',
        )

        embed.add_field(name='Gameday Starts At', value=human_timestamp(self.gameday.starts_at))
        embed.add_field(
            name='Current Registered Teammates',
            value=human_join((m.mention for m in self.gameday.attending_members)),
            inline=False,
        )

        return embed

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        await interaction.response.defer()

        # We need to add them to the gameday as a temporary member and then add them to the team.
        async with self.bot.safe_connection() as connection:
            await self.team.add_team_member(member_id=interaction.user.id, is_sub=True)
            await self.gameday.create_member(member_id=interaction.user.id, connection=connection, is_temporary_sub=True)

            await self.team.text_channel.send(
                f'I\'ve added a temporary sub to this team for the upcoming gameday. Say hello to {interaction.user.mention}!'
            )

            await interaction.followup.send(
                f'I\'ve added you as a sub to {self.team.display_name}, say hello to your temporary teammates in {self.team.text_channel.mention}!',
                ephemeral=True,
            )

            sub_finding = await self.gameday.getch_sub_finding(connection=connection)
            update_message = await sub_finding.fetch_update_message()
            if update_message is not None:
                embed = create_sub_finding_status_embed(self.gameday)
                await update_message.edit(embed=embed)

            message = await sub_finding.fetch_message()
            if self.gameday.voting.has_votes_needed:
                # We can end the sub finding sooner than expected.
                timer = await sub_finding.fetch_ends_at_timer(connection=connection)
                if timer is not None:
                    await timer.edit(expires=interaction.created_at)

                if message is not None:
                    await message.edit(view=None)

                return

            if message is not None:
                await message.edit(view=sub_finding.view, embed=sub_finding.view.embed)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        await interaction.response.defer()
        await interaction.followup.send('Cancelled sub finding.', ephemeral=True)
        await interaction.delete_original_response()


class SubFinder(discord.ui.View):
    """The implementation of a given sub finder for a team's gameday.

    The sub finder will only have one button and an embed. Upon a given sub clicking
    the button, they will have to manually press another "Confirm" button that they can
    sub for the given team, time, and gameday.

    This view does not dynamically find the data based on interaction data, so metadata
    needs to be passed in. This means, though, that the only instances of the :class:`SubFinder` should
    be active sub finders. Any **inactive** (completed) sub finders should be deleted.


    Parameters
    ----------
    gameday: :class:`Gameday`
        The gameday that this sub finder is for.

    Attributes
    ----------
    gameday: :class:`Gameday`
        The gameday that this sub finder is for.
    team: :class:`Team`
        The team that this sub finder is for.
    bot: :class:`FuryBot`
        The bot instance.

    Raises
    ------
    TeamDeleted
        This team has been deleted but the sub finder was initialized.
    """

    def __init__(self, gameday: Gameday, sub_finding: GamedaySubFinding) -> None:
        self.bot: FuryBot = gameday.bot
        self.gameday: Gameday = gameday
        self.sub_finding: GamedaySubFinding = sub_finding

        team = gameday.team
        if team is None:
            raise TeamDeleted(team_id=gameday.team_id)

        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        sub_finder_ends_at = self.sub_finding.ends_at
        if sub_finder_ends_at is None:
            raise ValueError('Cannot create a sub finder embed for a gameday that has no sub finder end time.')

        embed = self.team.embed(
            title='Sub Needed',
            description=f'{self.gameday.subs_needed} sub(s) are needed for the upcoming gameday. '
            f'This sub finder expires in {human_timestamp(sub_finder_ends_at)}',
        )

        embed.add_field(name='Gameday Starts At', value=human_timestamp(self.gameday.starts_at), inline=False)
        embed.add_field(
            name='Current Registered Teammates',
            value=human_join((m.mention for m in self.gameday.attending_members)),
            inline=False,
        )

        return embed

    @classmethod
    async def create(cls: Type[Self], *, gameday: Gameday, now: datetime.datetime) -> Self:
        bucket = gameday.bucket
        if bucket is None:
            raise ValueError('Cannot create a sub finder for a gameday that has no bucket.')

        sub_finding_channel = bucket.automatic_sub_finding_channel
        if sub_finding_channel is None:
            raise ValueError('Cannot create a sub finder for a gameday that has no sub finding channel.')

        comfy_sub_fiding_times = determine_comfy_sub_finding_times(starts_at=gameday.starts_at, now=now)
        if not comfy_sub_fiding_times.can_use_automatic_sub_finding:
            # TODO: Better error here
            raise ValueError('Cannot create a sub finder for a gameday that is too close to start.')

        bot = gameday.bot

        async with bot.safe_connection() as connection:
            sub_finding = await gameday.getch_sub_finding(connection=connection)

            self = cls(gameday=gameday, sub_finding=sub_finding)

            message = await sub_finding_channel.send(view=self, embed=self.embed)
            team_message = await self.team.text_channel.send(embed=create_sub_finding_status_embed(self.gameday))

            # Let's create a timer for when the sub finder should end
            timer_id = discord.utils.MISSING
            if bot.timer_manager:
                timer = await bot.timer_manager.create_timer(
                    comfy_sub_fiding_times.end,
                    'sub_finding_end',
                    guild_id=gameday.guild_id,
                    team_id=gameday.team_id,
                    gameday_id=gameday.id,
                )
                timer_id = timer.id

            await sub_finding.edit(
                connection=connection,
                starts_at=comfy_sub_fiding_times.start,
                ends_at=comfy_sub_fiding_times.end,
                ends_at_timer_id=timer_id,
                message_id=message.id,
                update_message_id=team_message.id,
            )

        return self

    @discord.ui.button(label='I Can Attend', style=discord.ButtonStyle.green)
    @default_button_doc_string
    async def can_attend(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """A button pressed by a user whenn they want to sub for the given gameday. This will launch a confirm view."""
        await interaction.response.defer(ephemeral=True)

        view = ConfirmSubFinding(gameday=self.gameday, target=interaction)
        return await interaction.edit_original_response(view=view, embed=view.embed)
