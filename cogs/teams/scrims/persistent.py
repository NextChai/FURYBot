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
from typing import TYPE_CHECKING, Optional, Tuple, TypeAlias, TypeVar, cast

import discord
from typing_extensions import Self

from utils import default_button_doc_string

from . import ScrimStatus

if TYPE_CHECKING:
    from bot import FuryBot

    from .scrim import Scrim

__all__: Tuple[str, ...] = ('HomeConfirm', 'AwayForceConfirm', 'AwayConfirm')

VT = TypeVar('VT', bound='discord.ui.View')
ButtonType: TypeAlias = discord.ui.Button[VT]


class HomeConfirm(discord.ui.View):
    """Represents the persistent view all  home members of a scrim must use to send the scrim
    off to the away team.

    Parameters
    ----------
    scrim: :class:`Scrim`
        The scrim this view is for.

    Attributes
    ----------
    scrim: :class:`Scrim`
        The scrim this view is for.
    bot: :class:`FuryBot`
        The main bot instance.
    """

    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: A discord embed to display information about the current state of the scrim to the home team."""
        scrim = self.scrim

        if scrim.status is ScrimStatus.pending_host:
            embed = self.bot.Embed(
                title='Confirm The Scrim',
                description='Use the "Confirm" button below to confirm you want to participate '
                f'in the scrim scheduled for {scrim.scheduled_for_formatted()},** playing '
                f'against {scrim.away_team.display_name}**.',
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
                    title=f'Waiting {scrim.away_team.display_name} Confirmation!',
                    description=f'This team has confirmed the scrim, now it\'s time for **{scrim.away_team.display_name}** '
                    f'to do the same. I\'m waiting for **{scrim.per_team - len(scrim.away_voter_ids)} vote(s) from '
                    'the opposing team** to confirm the scrim, then the scrim will be officially scheduled.',
                )
                embed.add_field(name='Scrim Date and Time', value=scrim.scheduled_for_formatted())
            else:
                embed = self.bot.Embed(
                    title='Scrim Scheduled',
                    description=f'A scrim on {scrim.scheduled_for_formatted()} **against {scrim.away_team.display_name}** has '
                    'been fully scheduled.',
                )
                embed.add_field(
                    name='How do I Scrim?',
                    value='When the scrim is scheduled to begin, '
                    'FuryBot will create a chat for both teams to communicate. In this chat, '
                    f'the home team, **{scrim.home_team.display_name}**, will create the private match for the away team, '
                    f'**{scrim.away_team.display_name}**, to join with. You decide how much and long you want to play. The scrim channel '
                    'will automatically be deleted after 5 hours. This chat is simply for the two teams to communicate, you should use '
                    'your private team voice chat for communication.',
                    inline=False,
                )

                if (
                    self.scrim.away_confirm_anyways_message_id is not None
                    and len(self.scrim.away_confirm_anyways_voter_ids) >= self.scrim.per_team // 2
                ):
                    force_started_value = f'The scrim was force started by: {", ".join(m.mention for m in self.scrim.away_confirm_anyways_voters)}'
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

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> Optional[bool]:
        """|coro|

        A check called every time before a button callback is invoked.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction to check.

        Returns
        -------
        Optional[:class:`bool`]
            ``True`` if the interaction passes the check, ``False`` if it fails, and ``None`` if the check is not
            applicable to the interaction.
        """
        members = self.scrim.home_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='home-confirm-confirm')
    @default_button_doc_string
    async def confirm(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Confirms a member on the home team wants to scrim."""
        try:
            await self.scrim.add_vote(interaction.user.id, self.scrim.home_id)
        except ValueError:
            return await interaction.response.send_message(content='You have already voted!', ephemeral=True)

        if not self.scrim.home_all_voted:
            # NOT all required members have voted, we need to edit the message
            # with the updated view
            return await interaction.response.edit_message(view=self, embed=self.embed)

        # We need to change the status and update the message,
        # all required members have voted
        await self.scrim.change_status(ScrimStatus.pending_away)
        await interaction.response.edit_message(view=None, embed=self.embed)

        # Now send to the other team
        channel = self.scrim.away_team.text_channel
        if not channel:
            # The channel was deleted, we need to cancel the scrim
            await self.scrim.cancel(reason='The away channel has been deleted.')
            return await interaction.response.send_message(
                'The away channel has been deleted. Cancelling the scrim...', ephemeral=True
            )

        view = AwayConfirm(self.scrim)
        message = await channel.send(
            embed=view.embed, view=view, content='@everyone', allowed_mentions=discord.AllowedMentions.all()
        )

        await self.scrim.edit(away_message_id=message.id)

    @discord.ui.button(label='Remove Confirmation', custom_id='home-confirm-remove')
    @default_button_doc_string
    async def remove_confirmation(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Allows an already confirmed member to remove their vote."""
        try:
            await self.scrim.remove_vote(interaction.user.id, self.scrim.home_id)
        except ValueError:
            return await interaction.response.send_message(
                content='You haven\'t voted, I\'m unable to remove you.', ephemeral=True
            )

        await interaction.response.edit_message(view=self, embed=self.embed)


class AwayForceConfirm(discord.ui.View):
    """An away team can vote to "force confirm" a given scrim if they're unable to reach enough members.
    This requires half of the scrim's "per-team" count to vote to force confirm.

    Parameters
    ----------
    scrim: :class:`Scrim`
        The scrim to force confirm.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    scrim: :class:`Scrim`
        The scrim to force confirm.
    required_to_confirm: :class:`int`
        The amount of votes required to force confirm.
    """

    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

        self.required_to_confirm = self.scrim.per_team // 2

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed to show for this view."""
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

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> Optional[bool]:
        """|coro|

        A check called every time before a button callback is invoked.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction to check.

        Returns
        -------
        Optional[:class:`bool`]
            ``True`` if the interaction passes the check, ``False`` if it fails, and ``None`` if the check is not
            applicable to the interaction.
        """
        members = self.scrim.away_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        # Check if they've voted, if they haven't then we need to yell at them
        if interaction.user.id not in self.scrim.away_confirm_anyways_voter_ids:
            return await interaction.response.send_message(
                'Hey, you haven\'t voted to force confirm this scrim yet!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Force Confirm', style=discord.ButtonStyle.success, custom_id='away-force-confirm')
    @default_button_doc_string
    async def force_confirm(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Votes the given member to force confirm the scrim."""
        self.scrim.away_confirm_anyways_voter_ids.append(interaction.user.id)

        await interaction.response.edit_message(embed=self.embed, view=self)

        await self.scrim.edit(away_confirm_anyways_voter_ids=self.scrim.away_confirm_anyways_voter_ids)

        if len(self.scrim.away_confirm_anyways_voter_ids) < self.required_to_confirm:
            # We don't have enough members to force confirm
            return

        # We have enough! Confirm the scrim.
        await self.scrim.change_status(ScrimStatus.scheduled)

        # Delete this message
        away_channel = self.scrim.away_team.text_channel
        if away_channel is None:
            # For whatever reason, this away channel has been deleted. We must cancel this scrim as the data
            # has been invalidated.
            return await self.scrim.cancel(reason='The away channel has been deleted.')

        message = await away_channel.fetch_message(cast(int, self.scrim.away_confirm_anyways_message_id))
        await message.delete()

        # Now update the home message
        home_channel = self.scrim.home_team.text_channel
        if home_channel is None:
            # Similar to before, if the home channel is also deleted, we must cancel the scrim.
            return await self.scrim.cancel(reason='The home channel has been deleted.')

        message = await home_channel.fetch_message(self.scrim.home_message_id)
        view = HomeConfirm(self.scrim)
        await message.edit(view=None, embed=view.embed)

        # Update the away message
        message = await away_channel.fetch_message(cast(int, self.scrim.away_message_id))
        view = AwayConfirm(self.scrim)
        await message.edit(view=None, embed=view.embed)


class AwayConfirm(discord.ui.View):
    """After all members on the :class:`HomeConfirm` view have confirmed, this view is shown to the away team.

    Parameters
    ----------
    scrim: :class:`Scrim`
        The scrim to show the view for.

    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    scrim: :class:`Scrim`
        The scrim to show the view for.
    """

    def __init__(self, scrim: Scrim, /) -> None:
        super().__init__(timeout=None)
        self.bot: FuryBot = scrim.bot
        self.scrim: Scrim = scrim

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed to show for this view."""
        scrim = self.scrim

        if scrim.status is ScrimStatus.pending_host:
            raise Exception('Scrim status did not transition correctly.')

        if scrim.status is ScrimStatus.pending_away:
            embed = self.bot.Embed(
                title='Scrim Incoming!',
                description=f'Team **{self.scrim.home_team.display_name}** would like to scrim your team on '
                f'{scrim.scheduled_for_formatted()}. Do you want to scrim? Press "Confirm" below to do so. '
                f'**{scrim.per_team - len(scrim.away_voter_ids)} vote(s) are needed** before the scrim '
                'is officially confirmed.',
            )
            embed.add_field(
                name='Confirmed Teammates',
                value=', '.join(m.mention for m in scrim.away_voters) or 'No one yet.',
                inline=False,
            )
            embed.add_field(name='Opposing Team:', value=', '.join(m.mention for m in scrim.home_voters), inline=False)
            return embed

        elif scrim.status is ScrimStatus.scheduled:
            embed = self.bot.Embed(
                title='Scrim Scheduled',
                description=f'Your scrim against **{self.scrim.home_team.display_name}** has been confirmed for '
                f'{scrim.scheduled_for_formatted()}.',
            )
            embed.add_field(
                name='How do I Scrim?',
                value='When the scrim is scheduled to begin, '
                'FuryBot will create a chat for both teams to communicate. In this chat, '
                f'the home team, **{scrim.home_team.display_name}**, will create the private match for the away team, '
                f'**{scrim.away_team.display_name}**, to join with. You decide how much and long you want to play. The scrim channel '
                'will automatically be deleted after 5 hours. This chat is simply for the two teams to communicate, you should use '
                'your private team voice chat for communication.',
                inline=False,
            )
            embed.add_field(name='Confirmed Teammates', value=', '.join(m.mention for m in scrim.away_voters), inline=False)
            embed.add_field(name='Opposing Team:', value=', '.join(m.mention for m in scrim.home_voters), inline=False)

            if (
                self.scrim.away_confirm_anyways_message_id is not None
                and len(self.scrim.away_confirm_anyways_voter_ids) >= self.scrim.per_team // 2
            ):
                force_started_value = (
                    f'The scrim was force started by: {", ".join(m.mention for m in self.scrim.away_confirm_anyways_voters)}'
                )
                embed.add_field(name='Scrim Force Started?', value=force_started_value, inline=False)

            return embed

        raise Exception('Unknown scrim status provided')

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> Optional[bool]:
        """|coro|

        A check called every time before a button callback is invoked.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction to check.

        Returns
        -------
        Optional[:class:`bool`]
            ``True`` if the interaction passes the check, ``False`` if it fails, and ``None`` if the check is not
            applicable to the interaction.
        """
        members = self.scrim.away_team.team_members
        if interaction.user.id not in members:
            return await interaction.response.send_message(
                'Hey, you aren\'t on this team so you can\'t vote!', ephemeral=True
            )

        return True

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='away-confirm-confirm')
    @default_button_doc_string
    async def confirm(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Confirms a given member on the away team to scrim at that given time."""
        try:
            await self.scrim.add_vote(interaction.user.id, self.scrim.away_id)
        except ValueError:
            return await interaction.response.send_message(content='You have already voted!', ephemeral=True)

        if self.scrim.away_all_voted:
            # All members have voted, change the status
            await self.scrim.change_status(ScrimStatus.scheduled)

            # We need to update our local message with NO view
            await interaction.response.edit_message(view=None, embed=self.embed)
        else:
            await interaction.response.edit_message(embed=self.embed, view=self)

        # And update the other message from the home team's chat:
        home_message = await self.scrim.home_message()
        if home_message is None:
            # If the home message has been deleted, we must cancel the scrim
            await interaction.response.send_message(
                'The home message has been deleted. Cancelling the scrim...', ephemeral=True
            )
            return await self.scrim.cancel(reason='The home message has been deleted.')

        view = HomeConfirm(self.scrim)
        await home_message.edit(embed=view.embed)

    @discord.ui.button(label='Force Confirm', custom_id='force-confirm-confirm')
    @default_button_doc_string
    async def force_confirm(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Launches a vote to force confirm the scrim. This can be done if the team is unable to get a full team
        but still wants to scrim."""
        if self.scrim.per_team < 2:
            return await interaction.response.send_message(
                f'You can not vote to force confirm if "per team" is less than 2.', ephemeral=True
            )

        away_text_channel = self.scrim.away_team.text_channel
        if away_text_channel is None:
            # This channel has been deleted, we must cancel the scrim
            await interaction.response.send_message(
                'The away channel has been deleted. Cancelling the scrim...', ephemeral=True
            )
            return await self.scrim.cancel(reason='The away channel has been deleted.')

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
        await self.scrim.edit(away_confirm_anyways_message_id=message.id)

    @discord.ui.button(label='Un-Confirm', custom_id='away-confirm-un-confirm')
    @default_button_doc_string
    async def un_confirm(self, interaction: discord.Interaction[FuryBot], button: ButtonType[Self]) -> None:
        """Allows a member to un-confirm their vote to scrim at that given time."""
        try:
            await self.scrim.remove_vote(interaction.user.id, self.scrim.away_id)
        except ValueError:
            return await interaction.response.send_message(content='You haven\'t voted!', ephemeral=True)

        return await interaction.response.edit_message(embed=self.embed, view=self)
