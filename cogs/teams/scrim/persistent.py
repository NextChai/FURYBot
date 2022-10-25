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
from typing import TYPE_CHECKING, Optional, TypeAlias, TypeVar, cast

import discord
from typing_extensions import Self

from . import ScrimStatus

if TYPE_CHECKING:
    from bot import FuryBot

    from .scrim import Scrim


VT = TypeVar('VT', bound='discord.ui.View')
ButtonType: TypeAlias = discord.ui.Button[VT]


class HomeConfirm(discord.ui.View):
    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

    @property
    def embed(self) -> discord.Embed:
        scrim = self.scrim

        print(scrim.status, scrim.status == ScrimStatus.pending_host)

        if scrim.status is ScrimStatus.pending_host:
            embed = self.bot.Embed(
                title='Confirm The Scrim',
                description='Use the "Confirm" button below to confirm you want to participate '
                f'in the scrim scheduled for {scrim.scheduled_for_formatted()},** playing '
                f'against {scrim.away_team.name}**.',
            )
            embed.add_field(
                name='Confirmed Members',
                value=', '.join([m.mention for m in scrim.home_voters] or ['No confirmed members on this team.']),
                inline=False,
            )
            embed.add_field(
                name='Vote(s) Needed',
                value=f'**{scrim.per_team - len(scrim.home_voter_ids)} vote(s) are needed** '
                'for this team to confirm the scrim.',
                inline=False,
            )
            return embed
        elif scrim.status in (ScrimStatus.pending_away, ScrimStatus.scheduled):
            if scrim.status is ScrimStatus.pending_away:
                embed = self.bot.Embed(
                    title=f'Waiting {scrim.away_team.name} Confirmation!',
                    description=f'This team has confirmed the scrim, now it\'s time for **{scrim.away_team.name}** '
                    f'to do the same. I\'m waiting for **{scrim.per_team - len(scrim.away_voter_ids)} vote(s) from '
                    'the opposing team** to confirm the scrim, then the scrim will be officially scheduled.',
                )
                embed.add_field(name='Scrim Date and Time', value=scrim.scheduled_for_formatted())
            else:
                embed = self.bot.Embed(
                    title='Scrim Scheduled!',
                    description=f'A scrim on {scrim.scheduled_for_formatted()} **against {scrim.away_team.name}** has '
                    'been fully scheduled.',
                )
                embed.add_field(
                    name='How do I Scrim?',
                    value='10 minutes before the scrim is scheduled to begin, '
                    'FuryBot will create a chat for both teams to communicate. In this chat, '
                    f'the home team, **{scrim.home_team.name}**, will create the private match for the away team, '
                    f'**{scrim.away_team.name}**, to join with. You decide how much and long you want to play. The scrim channel '
                    'will automatically be deleted after 5 hours.',
                    inline=False,
                )

                if (
                    self.scrim.away_confirm_anyways_message_id is not None
                    and len(self.scrim.away_confirm_anyways_voter_ids) >= self.scrim.per_team // 2
                ):
                    force_started_value = f'The scrim was force started by: {", ".join(m.mention for m in self.scrim.away_confirm_anyways_voters)}'
                else:
                    force_started_value = 'The scrim was not force started.'

                embed.add_field(name='Scrim Force Started?', value=force_started_value, inline=False)

            embed.add_field(
                name='Confirmed Teammates',
                value=', '.join([m.mention for m in scrim.home_voters] or ['No confirmed members on this team.']),
                inline=False,
            )
            embed.add_field(
                name='Confirmed Opposing Members',
                value=', '.join(
                    [m.mention for m in scrim.away_voters] or ['No members on the opposing team have confirmed.']
                ),
                inline=False,
            )
            return embed

        raise Exception('Unknown scrim status.')

    async def interaction_check(self, interaction: discord.Interaction) -> Optional[bool]:
        members = self.scrim.home_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='home-confirm-confirm')
    async def confirm(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        try:
            await self.scrim.add_vote(interaction.user.id, self.scrim.home_id)
        except ValueError:
            return await interaction.response.send_message(content='You have already voted!', ephemeral=True)

        if not self.scrim.home_all_voted:
            # NOT all required members have voted, we need to edit the message
            # with the updated view
            return await interaction.response.edit_message(view=self, embed=self.embed)

        # We need to change the status and update the message,
        # all requied members have voted
        await self.scrim.change_status(ScrimStatus.pending_away)
        await interaction.response.edit_message(view=None, embed=self.embed)

        # Now send to the other team
        channel = self.scrim.away_team.text_channel
        view = AwayConfirm(self.scrim)
        message = await channel.send(
            embed=view.embed, view=view, content='@everyone', allowed_mentions=discord.AllowedMentions.all()
        )

        self.away_message_id = message.id

        # Update the DB
        async with self.bot.safe_connection() as connection:
            await connection.execute('UPDATE teams.scrims SET away_message_id = $1 WHERE id = $2', message.id, self.scrim.id)

    @discord.ui.button(label='Remove Confirmation', custom_id='home-confirm-remove')
    async def remove_confirmation(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        try:
            await self.scrim.remove_vote(interaction.user.id, self.scrim.home_id)
        except ValueError:
            return await interaction.response.send_message(
                content='You haven\'t voted, I\'m unable to remove you.', ephemeral=True
            )

        await interaction.response.edit_message(view=self, embed=self.embed)


class AwayForceConfirm(discord.ui.View):
    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

        self.required_to_confirm = self.scrim.per_team // 2

    async def interaction_check(self, interaction: discord.Interaction) -> Optional[bool]:
        members = self.scrim.away_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        # Check if they've voted, if they havent then we need to yell at them
        if interaction.user.id not in self.scrim.away_confirm_anyways_voter_ids:
            return await interaction.response.send_message(
                'Hey, you haven\'t voted to force confirm this scrim yet!', ephemeral=True
            )

        return True

    @property
    def embed(self) -> discord.Embed:
        if len(self.scrim.away_confirm_anyways_voter_ids) >= self.required_to_confirm:
            # This vote has been passed, show an embed to represent it
            embed = self.bot.Embed(
                title='Vote to Force Confirm Passed',
                description='All required members have voted to force confirm. '
                f'The scrim will start at {self.scrim.scheduled_for_formatted()}.',
            )
        else:

            embed = self.bot.Embed(
                title='Vote to Force Confirm',
                description='A member on this team would like to force confirm the scrim. '
                f'This means that if **{self.required_to_confirm} members** confirm, the scrim '
                'will get scheduled without a full team. ',
            )

            embed.add_field(
                name='Members Required to Force Confirm',
                value=f'**{self.required_to_confirm - len(self.scrim.away_confirm_anyways_voters)} more member(s)** '
                'are required to force confirm.',
            )

        embed.add_field(
            name='Members Wanting to Force Confirm',
            value=', '.join([m.mention for m in self.scrim.away_confirm_anyways_voters]),
        )

        return embed

    @discord.ui.button(label='Force Confirm', style=discord.ButtonStyle.success, custom_id='away-force-confirm')
    async def force_confirm(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        self.scrim.away_confirm_anyways_voter_ids.append(interaction.user.id)

        await interaction.response.edit_message(embed=self.embed, view=self)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.scrims SET away_confirm_anyways_voter_ids = array_append(away_confirm_anyways_voter_ids, $1) '
                'WHERE id = $2',
                interaction.user.id,
                self.scrim.id,
            )

        if len(self.scrim.away_confirm_anyways_voter_ids) < self.required_to_confirm:
            # We don't have enough members to force econfirm
            return

        # We have enough! Confirm the scrim.
        await self.scrim.change_status(ScrimStatus.scheduled)

        # Delete this message
        away_channel = self.scrim.away_team.text_channel
        message = await away_channel.fetch_message(cast(int, self.scrim.away_confirm_anyways_message_id))
        await message.delete()

        # Now update the home message
        home_channel = self.scrim.home_team.text_channel
        message = await home_channel.fetch_message(self.scrim.home_message_id)
        view = HomeConfirm(self.scrim)
        await message.edit(view=None, embed=view.embed)

        # Update the away message
        message = await away_channel.fetch_message(cast(int, self.scrim.away_message_id))
        view = AwayConfirm(self.scrim)
        await message.edit(view=None, embed=view.embed)


class AwayConfirm(discord.ui.View):
    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

    @property
    def embed(self) -> discord.Embed:
        scrim = self.scrim

        if scrim.status is ScrimStatus.pending_host:
            raise Exception('Scrim status did not transition correctly.')

        if scrim.status is ScrimStatus.pending_away:

            embed = self.bot.Embed(
                title='Scrim Incoming!',
                description=f'Team **{self.scrim.home_team.name}** would like to scrim your team on '
                f'{scrim.scheduled_for_formatted()}. Do you want to scrim? Press "Confirm" below to do so. '
                f'**{scrim.per_team - len(scrim.away_voter_ids)} vote(s) are needed** before the scrim '
                'is officially confirmed.',
            )
            embed.add_field(name='Confirmed Teammates', value=', '.join(m.mention for m in scrim.away_voters))
            embed.add_field(name='Opposing Team:', value=', '.join(m.mention for m in scrim.home_voters))
            return embed

        elif scrim.status is ScrimStatus.scheduled:
            embed = self.bot.Embed(
                title='Scrim Scheduled',
                description=f'Your scrim against **{self.scrim.home_team.name}** has been confirmed for '
                f'{scrim.scheduled_for_formatted()}.',
            )
            embed.add_field(
                name='How do I Scrim?',
                value='10 minutes before the scrim is scheduled to begin, '
                'FuryBot will create a chat for bothho teams to communicate. In this chat, '
                f'the home team, **{scrim.away_team.name}**, will create the private match for the away team, '
                f'**{scrim.home_team.name}**, to join with. You decide how much and long you want to play. The scrim channel '
                'will automatically be deleted after 5 hours.',
                inline=False,
            )
            embed.add_field(name='Confirmed Teammates', value=', '.join(m.mention for m in scrim.away_voters))
            embed.add_field(name='Opposing Team:', value=', '.join(m.mention for m in scrim.home_voters))

            if (
                self.scrim.away_confirm_anyways_message_id is not None
                and len(self.scrim.away_confirm_anyways_voter_ids) >= self.scrim.per_team // 2
            ):
                force_started_value = (
                    f'The scrim was force started by: {", ".join(m.mention for m in self.scrim.away_confirm_anyways_voters)}'
                )
            else:
                force_started_value = 'The scrim was not force started.'

            embed.add_field(name='Scrim Force Started?', value=force_started_value, inline=False)

            return embed

        raise Exception('Unknown scrim status provided')

    async def interaction_check(self, interaction: discord.Interaction) -> Optional[bool]:
        members = self.scrim.away_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='away-confirm-confirm')
    async def confirm(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        try:
            await self.scrim.add_vote(interaction.user.id, self.scrim.away_id)
        except ValueError:
            return await interaction.response.send_message(content='You have already voted!', ephemeral=True)

        if self.scrim.away_all_voted:
            # All members have voted, change the status
            await self.scrim.change_status(ScrimStatus.scheduled)

        # We need to update our local message
        await interaction.response.edit_message(view=self, embed=self.embed)

        # And update the other message from the home team's chat:
        home_message = await self.scrim.home_message()
        view = HomeConfirm(self.scrim)
        await home_message.edit(embed=view.embed)

    @discord.ui.button(label='Force Confirm', custom_id='force-confirm-confirm')
    async def force_confirn(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        if self.scrim.per_team < 2:
            return await interaction.response.send_message(
                f'You can not vote to force confirm if "per team" is less than 2.', ephemeral=True
            )

        away_text_channel = self.scrim.away_team.text_channel

        if self.scrim.away_confirm_anyways_message_id:
            url = f'https://discordapp.com/channels/{away_text_channel.guild.id}/{away_text_channel.id}/{self.scrim.away_confirm_anyways_message_id}'
            return await interaction.response.send_message(
                f'A vote to force confirm has already been created. {url}', ephemeral=True
            )

        if len(self.scrim.away_voter_ids) < (self.scrim.per_team // 2):
            return await interaction.response.send_message(
                f'At least half of the required members ({(self.scrim.per_team // 2) - len(self.scrim.away_voter_ids)} more'
                'members) need to confirm before you can vote to force confirm.',
                ephemeral=True,
            )

        if self.scrim.scheduled_for - interaction.created_at > datetime.timedelta(minutes=30):
            try_again = self.scrim.scheduled_for - datetime.timedelta(minutes=30)
            return await interaction.response.send_message(
                f'You can not vote to force confirm unless you have 30 minutes before the scrim is scheduled to start. '
                f'Try again at: {discord.utils.format_dt(try_again, "F")} '
                f'({discord.utils.format_dt(try_again, "R")})',
                ephemeral=True,
            )

        # Launch the AwayForceConfirm view
        view = AwayForceConfirm(self.scrim)
        message = await away_text_channel.send(
            embed=view.embed, view=view, content='@everyone', allowed_mentions=discord.AllowedMentions.all()
        )
        self.scrim.away_confirm_anyways_message_id = message.id

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.scrims SET away_confirm_anyways_message_id = $1 WHERE id = $2', message.id, self.scrim.id
            )

    @discord.ui.button(label='Unconfirm', custom_id='away-confirm-unconfirm')
    async def unconfirm(self, interaction: discord.Interaction, button: ButtonType[Self]) -> None:
        try:
            await self.scrim.remove_vote(interaction.user.id, self.scrim.away_id)
        except ValueError:
            return await interaction.response.send_message(content='You haven\'t voted!', ephemeral=True)

        return await interaction.response.edit_message(embed=self.embed, view=self)
