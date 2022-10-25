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
from typing import TYPE_CHECKING, Callable, Annotated, Optional, TypeAlias, cast

import discord
from discord import app_commands
from discord.ext import commands
from cogs.teams.scrim import ScrimStatus

from utils import BaseCog, TimeTransformer, Context

from .scrim import Scrim
from .team import Team
from .transformers import TeamTransformer
from .views import TeamView

if TYPE_CHECKING:
    from bot import FuryBot


TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer]
FRONT_END_TEAM_TRANSFORM: TypeAlias = app_commands.Transform[Team, TeamTransformer(clamp_teams=True)]


class Teams(BaseCog):
    """A cog to manage teams and allow teams to create scrims and find subs."""

    team = app_commands.Group(
        name='team',
        description='Create and manage teams.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )

    scrim = app_commands.Group(name='scrim', description='Create and manage scrims.', guild_only=True)

    @team.command(name='create', description='Create a team.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(name='The name of the team.')
    async def team_create(self, interaction: discord.Interaction, name: str) -> discord.InteractionMessage:
        """|coro|

        Create a team.

        Parameters
        ----------
        name: :class:`str`
            The name of the team.
        """
        assert interaction.guild

        await interaction.response.defer()

        team = await Team.create(name, guild=interaction.guild, bot=self.bot)
        view = TeamView(team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @team.command(name='manage', description='Manage a team. Assign members, subs, captains, scrims, etc.')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(team='The team you want to manage.')
    async def team_manage(self, interaction: discord.Interaction, team: TEAM_TRANSFORM) -> discord.InteractionMessage:
        """|coro|

        A command used to manage a team. This will launch an depth view in which you can manage the team.

        Use this command to add subs, remove subs, add members, remove members, create extra channels, assign captain roles,
        etc.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to manage.
        """
        await interaction.response.defer()

        view = TeamView(team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @scrim.command(name='create', description='Create a scrim')
    @app_commands.describe(
        team='The team you want to scrim against.',
        when='When you want to scrim the other team. For ex: "Tomorrow at 4pm", "Next tuesday at 12pm", etc.',
        per_team='The amount of players per team. For ex: 5, 3, 2, etc.',
    )
    async def scrim_create(
        self,
        interaction: discord.Interaction,
        team: FRONT_END_TEAM_TRANSFORM,
        when: Annotated[TimeTransformer, TimeTransformer(default='n/a')],
        per_team: app_commands.Range[int, 2, 10],
    ) -> discord.InteractionMessage:
        """|coro|

        A command used to create a scrim.

        Parameters
        ----------
        team: :class:`Team`
            The team you want to scrim against.
        when: :class:`TimeTransformer`
            When you want to scrim the other team. For ex: "Tomorrow at 4pm", "Next tuesday at 12pm", etc.
        per_team: :class:`int`
            The amount of players per team. For ex: 5, 3, 2, etc.
        """
        assert isinstance(interaction.channel, (discord.abc.GuildChannel, discord.Thread))
        assert interaction.channel.category
        assert when.dt

        await interaction.response.defer(ephemeral=True)

        home_team = Team.from_category(interaction.channel.category.id, bot=self.bot)

        scrim = await Scrim.create(
            when.dt, home_team=home_team, away_team=team, per_team=per_team, creator_id=interaction.user.id, bot=self.bot
        )

        return await interaction.edit_original_response(
            content=f'A scrim for {scrim.scheduled_for_formatted()} has been created against {team.display_name}.'
        )

    @commands.command(name='_team_import', hidden=True)
    @commands.is_owner()
    async def team_import(self, ctx: Context) -> discord.Message:
        text_channel = cast(discord.TextChannel, ctx.channel)
        category_channel = cast(discord.CategoryChannel, text_channel.category)

        voice_channel = discord.utils.find(lambda c: isinstance(c, discord.VoiceChannel), category_channel.channels)
        if not voice_channel:
            return await ctx.send('No voice channel found.')

        default_check: Callable[[discord.Message], Optional[bool]] = (
            lambda message: message.author == ctx.author and message.channel == ctx.channel
        )

        # Get the members now
        await ctx.send('Send members.')
        member_message: discord.Message = await self.bot.wait_for('message', check=default_check, timeout=None)
        members = member_message.mentions

        # Get the subs
        await ctx.send('Send subs.')
        sub_message: discord.Message = await self.bot.wait_for('message', check=default_check, timeout=None)
        subs = sub_message.mentions

        # Get the captain role
        await ctx.send('Send captain roles.')
        captain_message: discord.Message = await self.bot.wait_for('message', check=default_check, timeout=None)
        captain_roles = captain_message.role_mentions

        async with ctx.typing():
            async with self.bot.safe_connection() as connection:
                data = await connection.fetchrow(
                    'INSERT INTO teams.settings(guild_id, category_channel_id, text_channel_id, voice_channel_id, name, captain_role_ids) '
                    'VALUES($1, $2, $3, $4, $5, $6) '
                    'RETURNING *',
                    category_channel.guild.id,
                    category_channel.id,
                    text_channel.id,
                    voice_channel.id,
                    category_channel.name,
                    captain_roles,
                )

                assert data

                team = Team(self.bot, **dict(data))
                self.bot.team_cache[team.id] = team

            for member in members:
                await team.add_team_member(member.id)

            for sub in subs:
                await team.add_team_member(sub.id, is_sub=True)

        view = TeamView(team, target=ctx)
        return await ctx.send(view=view, embed=view.embed)

    @classmethod
    def _create_scrim_cancelled_message(cls, bot: FuryBot, scrim: Scrim) -> discord.Embed:
        home_embed = bot.Embed(
            title='This scrim has been cancelled.',
            description='There were not enough votes to start the scrim.\n\n'
            f'**Votes Needed from {scrim.home_team.display_name,}**: {scrim.per_team - len(scrim.home_voter_ids)}\n'
            f'**Votes Needed from {scrim.away_team.display_name}**: {scrim.per_team - len(scrim.away_voter_ids)}',
        )
        home_embed.add_field(
            name=f'{scrim.home_team.display_name} Team Votes',
            value=', '.join(m.mention for m in scrim.home_voters) or 'No members have voted.',
        )
        home_embed.add_field(
            name=f'{scrim.home_team.display_name} Team Votes',
            value=', '.join(m.mention for m in scrim.away_voters) or 'No members have voted.',
        )

        return home_embed

    # Timer listeners for scrim
    @commands.Cog.listener('on_scrim_scheduled_timer_complete')
    async def on_scrim_scheduled_timer_complete(self, *, scrim_id: int) -> None:
        scrim = self.bot.team_scrim_cache.get(scrim_id)
        if scrim is None:
            return

        # If the scrim isn't scheduled we want to edit the messages and say that the scrim didnt start
        if scrim.status is not ScrimStatus.scheduled:
            cancelled_embed = self._create_scrim_cancelled_message(self.bot, scrim)

            home_message = await scrim.home_message()
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

        embed = self.bot.Embed(
            title=f'{scrim.home_team.display_name} vs {scrim.away_team.display_name}',
            description=f'Scrim has been scheduled and confirmed for {scrim.scheduled_for_formatted()}',
        )
        embed.add_field(name=scrim.home_team.display_name, value=', '.join(m.mention for m in scrim.home_voters))
        embed.add_field(name=scrim.away_team.display_name, value=', '.join(m.mention for m in scrim.away_voters))
        embed.set_footer(text='This channel will automatically delete in 4 hours.')
        await scrim_chat.send(embed=embed)

        # Create a timer to delete this channel in 4 hours and delete the scrim.
        scrim_delete_timer = await self.bot.timer_manager.create_timer(
            discord.utils.utcnow() + datetime.timedelta(hours=4), 'scrim_delete', scrim_id=scrim_id
        )
        await scrim.edit(scrim_delete_timer_id=scrim_delete_timer.id)

    @commands.Cog.listener()
    async def on_scrim_delete_timer_complete(self, *, scrim_id: int) -> None:
        scrim = self.bot.team_scrim_cache.pop(scrim_id, None)
        if not scrim:
            return

        # Delete the scrim chat
        chat = scrim.scrim_chat
        if chat is not None:
            await chat.delete()

        # Delete this scrim from the database
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.scrims WHERE id = $1', scrim.id)

    @commands.Cog.listener()
    async def on_scrim_reminder_timer_complete(self, *, scrim_id: int) -> None:
        scrim = self.bot.team_scrim_cache.get(scrim_id)
        if not scrim:
            return

        home_message = await scrim.home_message()
        if scrim.status is ScrimStatus.scheduled:
            content = f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()}. Please be ready, a team chat will be created at that time.'
            await home_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))

            away_message = await scrim.away_message()
            if away_message:
                await away_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))

        elif scrim.status is ScrimStatus.pending_host:
            content = f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()} '
            'and I do not have enough votes from this team to confirm the scrim. **I\'m going to cancel this '
            'scrim as it\'s very unlikely the other team will confirm in time**.'
            await home_message.reply(content, allowed_mentions=discord.AllowedMentions(everyone=True))
            await scrim.cancel()

        elif scrim.status is ScrimStatus.pending_away:
            content = f'@everyone, this scrim is scheduled to start on {scrim.scheduled_for_formatted()} and I\'m waiting '
            f'on {scrim.per_team - len(scrim.away_voter_ids)} vote(s) from {scrim.away_team.display_name}.'


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
