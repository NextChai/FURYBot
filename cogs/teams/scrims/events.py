"""
Contributor-Only License v1.0

This file is licensed under the Contributor-Only License. Usage is restricted to 
non-commercial purposes. Distribution, sublicensing, and sharing of this file 
are prohibited except by the original owner.

Modifications are allowed solely for contributing purposes and must not 
misrepresent the original material. This license does not grant any 
patent rights or trademark rights.

Full license terms are available in the LICENSE file at the root of the repository.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Tuple

import discord
from discord.ext import commands

from utils import BaseCog

from .scrim import ScrimStatus

if TYPE_CHECKING:
    from bot import FuryBot

    from .scrim import Scrim

__all__: Tuple[str, ...] = ('ScrimEventListener',)


class ScrimEventListener(BaseCog):
    @classmethod
    def _create_scrim_cancelled_message(cls, bot: FuryBot, scrim: Scrim) -> discord.Embed:
        """Creates an embed detailing that a scrim has been cancelled.

        Parameters
        ----------
        bot: :class:`FuryBot`
            The bot instance.
        scrim: :class:`Scrim`
            The scrim that was cancelled.

        Returns
        -------
        :class:`discord.Embed`
            The embed detailing that a scrim has been cancelled.
        """
        home_team_display_name = scrim.home_team and scrim.home_team.display_name or '<Home Team Deleted>'
        away_team_display_name = scrim.away_team and scrim.away_team.display_name or '<Away Team Deleted>'

        home_embed = bot.Embed(
            title='This scrim has been cancelled.',
            description='There were not enough votes to start the scrim.\n\n'
            f'**Votes Needed from {home_team_display_name}**: {scrim.per_team - len(scrim.home_voter_ids)}\n'
            f'**Votes Needed from {away_team_display_name}**: {scrim.per_team - len(scrim.away_voter_ids)}',
        )
        home_embed.add_field(
            name=f'{home_team_display_name} Team Votes',
            value=', '.join(m.mention for m in scrim.home_voters) or 'No members have voted.',
        )
        home_embed.add_field(
            name=f'{away_team_display_name} Team Votes',
            value=', '.join(m.mention for m in scrim.away_voters) or 'No members have voted.',
        )

        return home_embed

    # Timer listeners for scrim
    @commands.Cog.listener('on_scrim_scheduled_timer_complete')
    async def on_scrim_scheduled_timer_complete(self, *, scrim_id: int, guild_id: int) -> None:
        """|coro|

        A scrim listener that is called when a scrim has been scheduled for a certain time. This
        will check if the scrim has been confirmed then create the messages, views, and chats for the scrim.

        Parameters
        ----------
        scrim_id: :class:`int`
            The id of the scrim that has been scheduled.
        guild_id: :class:`int`
            The id of the guild that the scrim is in.
        """
        scrim = self.bot.get_scrim(scrim_id, guild_id)
        if scrim is None:
            return

        home_team = scrim.home_team
        away_team = scrim.away_team
        if not home_team or not away_team:
            # One of these teams has been deleted, we must cancel this scrim
            return await scrim.cancel(reason='One of the teams has been deleted.')

        # If the scrim isn't scheduled we want to edit the messages and say that the scrim didn't start
        if scrim.status is not ScrimStatus.scheduled:
            cancelled_embed = self._create_scrim_cancelled_message(self.bot, scrim)

            home_message = await scrim.home_message()
            if home_message is None:
                # The scrim home message has been deleted, thus the scrim must be invalidated.
                return await scrim.cancel(
                    reason='The home message has been deleted. Assuming the scrim has been invalidated.'
                )

            await home_message.edit(embed=cancelled_embed, view=None, content=None)

            # Reply to it and ping the members of this change
            await home_message.reply(
                content='@everyone, please note this scrim did not start.',
                allowed_mentions=discord.AllowedMentions(everyone=True),
            )

            away_message = await scrim.away_message()
            if away_message is not None:
                await home_message.edit(embed=cancelled_embed, view=None, content=None)
                await home_message.reply(
                    content='@everyone, please note this scrim did not start.',
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )

            return

        scrim_chat = await scrim.create_scrim_chat()
        if scrim_chat is None:
            # This scrim could not be created, we cannot do anything else
            return

        embed = self.bot.Embed(
            title=f'{home_team.display_name} vs {away_team.display_name}',
            description=f'Scrim has been scheduled and confirmed for {scrim.scheduled_for_formatted()}',
        )
        embed.add_field(name=home_team.display_name, value=', '.join(m.mention for m in scrim.home_voters))
        embed.add_field(name=away_team.display_name, value=', '.join(m.mention for m in scrim.away_voters))
        embed.set_footer(text='This channel will automatically delete in 4 hours.')
        await scrim_chat.send(embed=embed)

        # Create a timer to delete this channel in 4 hours and delete the scrim.
        if self.bot.timer_manager:
            scrim_delete_timer = await self.bot.timer_manager.create_timer(
                discord.utils.utcnow() + datetime.timedelta(hours=4), 'scrim_delete', scrim_id=scrim_id, guild_id=guild_id
            )
            await scrim.edit(scrim_delete_timer_id=scrim_delete_timer.id)

    @commands.Cog.listener('on_scrim_delete_timer_complete')
    async def on_scrim_delete_timer_complete(self, *, scrim_id: int, guild_id: int) -> None:
        """|coro|

        After N time the scrim and its chats are automatically deleted. This is what this listener
        is for.

        Parameters
        ----------
        scrim_id: :class:`int`
            The id of the scrim that has ended.
        guild_id: :class:`int`
            The id of the guild that the scrim is in.
        """
        scrim = self.bot.remove_scrim(scrim_id, guild_id)
        if not scrim:
            return

        # Delete the scrim chat
        chat = scrim.scrim_chat
        if chat is not None:
            await chat.delete()

        # Delete this scrim from the database
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.scrims WHERE id = $1', scrim.id)

    @commands.Cog.listener('on_scrim_reminder_timer_complete')
    async def on_scrim_reminder_timer_complete(self, *, scrim_id: int, guild_id: int) -> None:
        """|coro|

        The scrim reminder timer. This will send a reminder to both teams that the scrim is about to start
        in 30 minutes.

        Parameters
        ----------
        scrim_id: :class:`int`
            The id of the scrim that is about to start.
        guild_id: :class:`int`
            The id of the guild that the scrim is in.
        """
        scrim = self.bot.get_scrim(scrim_id, guild_id)
        if not scrim:
            return

        home_team = scrim.home_team
        away_team = scrim.away_team
        if not home_team or not away_team:
            # One of these teams has been deleted, we must cancel this scrim
            return await scrim.cancel(reason='One of the teams has been deleted.')

        home_message = await scrim.home_message()
        if scrim.status is ScrimStatus.scheduled:
            if home_message is None:
                # We have no home message, we must cancel this scrim
                return await scrim.cancel(reason='The home message has been deleted.')

            content = f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()}. Please be ready, a team chat will be created at that time.'
            await home_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))

            away_message = await scrim.away_message()
            if away_message:
                await away_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))

        elif scrim.status is ScrimStatus.pending_host:
            if home_message is None:
                # We have no home message, we must cancel this scrim
                return await scrim.cancel(reason='The home message has been deleted.')

            content = (
                f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()} '
                'and I do not have enough votes from this team to confirm the scrim. **I\'m going to cancel this '
                'scrim as it\'s very unlikely the other team will confirm in time**.'
            )
            await home_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))
            await scrim.cancel()

        elif scrim.status is ScrimStatus.pending_away:
            content = (
                f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()} and I\'m waiting '
                f'on {scrim.per_team - len(scrim.away_voter_ids)} vote(s) from {away_team.display_name}.'
            )
