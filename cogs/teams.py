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

from typing import TYPE_CHECKING, Any, List, Optional, TypeAlias, Union

import asyncpg
import discord
from discord import app_commands

from utils import assertion
from utils.bases.cog import BaseCog

if TYPE_CHECKING:
    from bot import FuryBot


class TeamTransformer(app_commands.Transformer):
    async def autocomplete(
        self, interaction: discord.Interaction, value: Union[int, float, str], /
    ) -> List[app_commands.Choice[Union[int, float, str]]]:
        # Show available teams
        bot: FuryBot = interaction.client  # type: ignore

        return [app_commands.Choice(name=team['name'], value=str(team['id'])) for team in bot.team_cache.values()]

    async def transform(self, interaction: discord.Interaction, value: Any, /) -> asyncpg.Record:
        if not value.isdigit():
            raise Exception('Invalid team selected.')

        bot: FuryBot = interaction.client  # type: ignore
        return bot.team_cache[int(value)]


TEAM_TRANSFORM: TypeAlias = app_commands.Transform[asyncpg.Record, TeamTransformer]


class Teams(BaseCog):

    team = app_commands.Group(
        name='team',
        description='Create and manage teams.',
        guild_only=True,
        default_permissions=discord.Permissions(moderate_members=True),
    )
    team_members = app_commands.Group(name='members', description='Manage team members.', parent=team)
    team_subs = app_commands.Group(name='subs', description='Manage team subs.', parent=team)

    @team.command(name='create', description='Create a team.')
    @app_commands.describe(name='The name of the team.')
    @app_commands.guild_only()
    async def team_create(self, interaction: discord.Interaction, name: str) -> None:
        assert interaction.guild

        if name.lower() in (team['name'].lower() for team in self.bot.team_cache.values()):
            return await interaction.response.send_message(f'Team with the name `{name}` already exists.', ephemeral=True)

        category = await interaction.guild.create_category(
            name=name,
            overwrites={interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)},
            reason='New team.',
        )
        text_channel = await category.create_text_channel(name='team-chat')
        voice_channel = await category.create_voice_channel(name='Team Voice')

        async with self.bot.safe_connection() as connection:
            data = await connection.fetchrow(
                """
                INSERT INTO teams.settings(category_id, channels, name) VALUES($1, $2, $3)
                RETURNING *
                """,
                category.id,
                [text_channel.id, voice_channel.id],
                name,
            )

            assert data

        self.bot.team_cache[data['id']] = data
        return await interaction.response.send_message(
            f'Team `{name}` has been created. Team general chat {text_channel.mention}.', ephemeral=True
        )

    @team.command(name='delete', description='Delete a team.')
    @app_commands.describe(team='The team to delete.')
    async def team_delete(self, interaction: discord.Interaction, team: TEAM_TRANSFORM) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.settings WHERE id = $1', team['id'])

        self.bot.team_cache.pop(team['id'], None)
        return await interaction.response.send_message(f'Team `{team["name"]}` has been deleted.', ephemeral=True)

    @team.command(name='view', description='View stats about a specific team.')
    async def team_view(self, interaction: discord.Interaction, team: TEAM_TRANSFORM) -> None:
        assert interaction.guild

        async with self.bot.safe_connection() as connection:
            team_roster_data = await connection.fetch('SELECT * FROM teams.members WHERE team_id = $1', team['id'])

        embed = self.bot.Embed(
            title=team['name'],
        )

        category = interaction.guild.get_channel(team['category_id'])
        embed.add_field(name='Category', value=category and category.name or "Category Deleted.")

        channel_fmt: List[str] = []
        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                channel_fmt.append(f'- {channel.mention}')
            else:
                channel_fmt.append(f'- Channel `{channel_id}` deleted.')

        embed.add_field(name='Channels', value='\n'.join(channel_fmt))

        members_fmt: List[str] = []
        subs_fmt: List[str] = []
        for entry in team_roster_data:
            mention_fmt = f'<@{entry["member_id"]}>'

            if entry['is_sub']:
                subs_fmt.append(f'- {mention_fmt}')
            else:
                members_fmt.append(f'- {mention_fmt}')

        if members_fmt:
            embed.add_field(name='Members', value='\n'.join(members_fmt))

        if subs_fmt:
            embed.add_field(name='Subs', value='\n'.join(subs_fmt))

        return await interaction.response.send_message(embed=embed)

    @team_members.command(name='add', description='Add a team member.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the team.')
    async def team_members_add(self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member) -> None:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute('INSERT INTO teams.members(team_id, member_id) VALUES($1, $2)', team['id'], member.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                await channel.edit(sync_permissions=True)

        await interaction.edit_original_response(content=f'Added {member.mention} to the {team["name"]} team.')

    @team_members.command(name='remove', description='Remove a team member.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_members_remove(
        self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member
    ) -> None:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                await channel.edit(sync_permissions=True)

        await interaction.edit_original_response(content=f'Removed {member.mention} from the {team["name"]} team.')

    @team_members.command(name='demote', description='Demote a team member to a sub.')
    async def team_members_demote(
        self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member
    ) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.members SET is_sub = True WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Demoted {member.mention} on the `{team["name"]}` team.', ephemeral=True
        )

    @team_subs.command(name='add', description='Add a member to the subs list.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the subs list.')
    async def team_subs_add(self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member) -> None:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'INSERT INTO teams.members(team_id, member_id, is_sub) VALUES($1, $2, True)', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                await channel.edit(sync_permissions=True)

        await interaction.edit_original_response(content=f'Added {member.mention} to {team["name"]}\'s sub roster.')

    @team_subs.command(name='remove', description='Remove a sub from a team.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_subs_remove(self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member) -> None:
        assert interaction.guild

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                await channel.edit(sync_permissions=True)

        await interaction.edit_original_response(content=f'Removed {member.mention} from {team["name"]}\'s sub roster.')

    @team_subs.command(name='promote', description='Promote a team\'s sub to be apart of the main roster.')
    async def team_subs_promote(
        self, interaction: discord.Interaction, team: TEAM_TRANSFORM, member: discord.Member
    ) -> None:
        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.members SET is_sub = False WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Promoted {member.mention} on the `{team["name"]}` team.', ephemeral=True
        )


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
