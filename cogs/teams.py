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

import asyncio
import difflib
from typing import TYPE_CHECKING, Any, Coroutine, List, Optional, TypeAlias, Union

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

        team_mapping = {team['name']: team for team in bot.team_cache.values()}
        if not team_mapping:
            return []

        if not value:
            return [
                app_commands.Choice(name=team['name'], value=str(team['id'])) for team in list(bot.team_cache.values())[:20]
            ]

        similar: List[str] = await bot.wrap(difflib.get_close_matches, str(value), team_mapping.keys(), n=20)  # type: ignore
        return [
            app_commands.Choice(name=team_mapping[entry]['name'], value=str(team_mapping[entry]['id'])) for entry in similar
        ]

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
    team_captains = app_commands.Group(name='captains', description='Manage team captainis.', parent=team)

    async def _sync_channels(self, guild: discord.Guild, channel_ids: List[int]) -> None:
        for channel_id in channel_ids:
            channel = assertion(guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]])
            if channel:
                await channel.edit(sync_permissions=True)

    async def fetch_team(self, category: discord.CategoryChannel) -> Optional[asyncpg.Record]:
        return discord.utils.find(lambda x: x['category_id'] == category.id, self.bot.team_cache.values())

    @team.command(name='get', description='Get the team(s) that a specific member is on.')
    async def team_get(self, interaction: discord.Interaction, member: discord.Member) -> None:
        async with self.bot.safe_connection() as connection:
            data = await connection.fetch('SELECT * FROM teams.members WHERE member_id = $1', member.id)

        if not data:
            return await interaction.response.send_message(f'{member.mention} is not on any teams.')

        fmt: List[str] = []
        for entry in data:
            team = self.bot.team_cache[entry['team_id']]
            fmt.append(
                f'**{team["name"]}**: {"Is on the main roster." if not entry["is_sub"] else "Is a sub for the team."}'
            )

        return await interaction.response.send_message(f'{member.mention} is on:\n' + '\n'.join(fmt))

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
    async def team_delete(self, interaction: discord.Interaction, team: Optional[TEAM_TRANSFORM] = None) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            await connection.execute('DELETE FROM teams.settings WHERE id = $1', team['id'])

        futures: List[Coroutine[Any, Any, Any]] = []
        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                futures.append(channel.delete(reason='Team deleted.'))

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            futures.append(category.delete(reason='Team deleted.'))

        await asyncio.gather(*futures)

        self.bot.team_cache.pop(team['id'], None)
        return await interaction.response.send_message(f'Team {team["name"]} has been deleted.', ephemeral=True)

    @team.command(name='info', description='View stats about a specific team.')
    @app_commands.describe(team='The team to get information on.')
    async def team_info(self, interaction: discord.Interaction, team: Optional[TEAM_TRANSFORM] = None) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            team_roster_data = await connection.fetch('SELECT * FROM teams.members WHERE team_id = $1', team['id'])

        embed = self.bot.Embed(
            title=team['name'], description=f'Below displays some inforamtion about {team["name"]}.', author=interaction.user
        )

        category = interaction.guild.get_channel(team['category_id'])
        embed.add_field(name='Category', value=category and category.name or "Category Deleted.", inline=False)

        channel_fmt: List[str] = []
        for channel_id in team['channels']:
            channel = assertion(
                interaction.guild.get_channel(channel_id), Optional[Union[discord.TextChannel, discord.VoiceChannel]]
            )
            if channel:
                channel_fmt.append(f'- {channel.mention}')
            else:
                channel_fmt.append(f'- Channel `{channel_id}` deleted.')

        embed.add_field(name='Channels', value='\n'.join(channel_fmt), inline=False)

        members_fmt: List[str] = []
        subs_fmt: List[str] = []
        for entry in team_roster_data:
            mention_fmt = f'<@{entry["member_id"]}>'

            if entry['is_sub']:
                subs_fmt.append(f'- {mention_fmt}')
            else:
                members_fmt.append(f'- {mention_fmt}')

        captains_fmt: List[str] = []
        for entry in team['captain_roles']:
            role = interaction.guild.get_role(entry)
            if role:
                captains_fmt.append(f'- {role.mention}')

        embed.add_field(name='Members', value='\n'.join(members_fmt or ['No members on this team.']), inline=False)
        embed.add_field(name='Subs', value='\n'.join(subs_fmt or ['No subs on this team.']), inline=False)
        embed.add_field(name='Captains', value='\n'.join(captains_fmt or ['No captains on this team.']))
        return await interaction.response.send_message(embed=embed)

    @team_members.command(name='add', description='Add a team member.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the team.')
    async def team_members_add(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if member_data:
                return await interaction.response.send_message('This member is already on the team.', ephemeral=True)

            await connection.execute('INSERT INTO teams.members(team_id, member_id) VALUES($1, $2)', team['id'], member.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Added {member.mention} to the {team["name"]} team.')

    @team_members.command(name='bulk_add', description='Bulk add members to a team.')
    @app_commands.describe(team="The team to add the member to.")
    async def team_members_bulk_add(
        self,
        interaction: discord.Interaction,
        team: Optional[TEAM_TRANSFORM] = None,
        member1: Optional[discord.Member] = None,
        member2: Optional[discord.Member] = None,
        member3: Optional[discord.Member] = None,
        member4: Optional[discord.Member] = None,
        member5: Optional[discord.Member] = None,
        member6: Optional[discord.Member] = None,
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        members = {
            member.id: member for member in [member1, member2, member3, member4, member5, member6] if member is not None
        }

        async with self.bot.safe_connection() as connection:
            members_data = await connection.fetch(
                "SELECT member_id FROM teams.members WHERE member_id = ANY($1) AND team_id = $2",
                list(members.keys()),
                team['id'],
            )
            for entry in members_data:
                members.pop(entry['member_id'], None)

            await connection.executemany(
                'INSERT INTO teams.members(team_id, member_id) VALUES($1, $2)',
                [(team['id'], member_id) for member_id in members.keys()],
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            for member in members.values():
                await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(
            content='Added {} to the team.'.format(', '.join(m.mention for m in members.values()))
        )

    @team_members.command(name='remove', description='Remove a team member.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_members_remove(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> Optional[discord.InteractionMessage]:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.edit_original_response(content='This member is not on the team.')

            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Removed {member.mention} from the {team["name"]} team.')

    @team_members.command(name='demote', description='Demote a team member to a sub.')
    @app_commands.describe(team='The team to demote the member on.', member='The member to demote.')
    async def team_members_demote(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.response.send_message('This member is not on the team.', ephemeral=True)

            await connection.execute(
                'UPDATE teams.members SET is_sub = True WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Demoted {member.mention} on the {team["name"]} team.', ephemeral=True
        )

    @team_subs.command(name='add', description='Add a member to the subs list.')
    @app_commands.describe(team="The team to add the member to.", member='The member to add to the subs list.')
    async def team_subs_add(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if member_data:
                return await interaction.response.send_message('This member is already on the team.', ephemeral=True)

            await connection.execute(
                'INSERT INTO teams.members(team_id, member_id, is_sub) VALUES($1, $2, True)', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(member, view_channel=True, reason='Requested to add member to team.')

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Added {member.mention} to {team["name"]}\'s sub roster.')

    @team_subs.command(name='remove', description='Remove a sub from a team.')
    @app_commands.describe(team="The team to remove the member from.", member='The member to remove from the team.')
    async def team_subs_remove(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.response.send_message('This member is not on the team.', ephemeral=True)

            await connection.execute(
                'DELETE FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(member, None)
            await category.edit(overwrites=overwrites)

        await self._sync_channels(interaction.guild, team['channels'])
        await interaction.edit_original_response(content=f'Removed {member.mention} from {team["name"]}\'s sub roster.')

    @team_subs.command(name='promote', description='Promote a team\'s sub to be apart of the main roster.')
    @app_commands.describe(member='The member to promote.', team='The team to promote the member on.')
    async def team_subs_promote(
        self, interaction: discord.Interaction, member: discord.Member, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        async with self.bot.safe_connection() as connection:
            member_data = await connection.fetchval(
                'SELECT member_id FROM teams.members WHERE team_id = $1 AND member_id = $2', team['id'], member.id
            )
            if not member_data:
                return await interaction.response.send_message('This member is not on the team.', ephemeral=True)

            await connection.execute(
                'UPDATE teams.members SET is_sub = False WHERE member_id = $1 AND team_id = $2', member.id, team['id']
            )

        return await interaction.response.send_message(
            f'Promoted {member.mention} on the {team["name"]} team.', ephemeral=True
        )

    @team_captains.command(name='add', description='Add a team captain role.')
    @app_commands.describe(role='The role to add.', team='The team to add the captain role to.')
    async def team_captains_add(
        self, interaction: discord.Interaction, role: discord.Role, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        if role.id in team['captain_roles']:
            return await interaction.response.send_message('This role is already a captain.', ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_roles = array_append(captain_roles, $1) WHERE id = $2',
                role.id,
                team['id'],
            )

        team['captain_roles'].append(role.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            await category.set_permissions(role, view_channel=True, reason='Adding new captain.')

        await self._sync_channels(interaction.guild, team['channels'])
        return await interaction.response.send_message(f'Added {role.mention} to the {team["name"]} team.', ephemeral=True)

    @team_captains.command(name='remove', description='Remove a team captain role.')
    @app_commands.describe(role='The role to remove.', team='The team to remove the captain role from.')
    async def team_captains_remove(
        self, interaction: discord.Interaction, role: discord.Role, team: Optional[TEAM_TRANSFORM] = None
    ) -> None:
        assert interaction.guild

        category = getattr(interaction.channel, 'category', None)
        if not category:
            return await interaction.response.send_message(
                "Please use this command in a channel that has a category or mention the team parameter."
            )

        if not team:
            team = await self.fetch_team(category)
            if not team:
                return await interaction.response.send_message(
                    'You did not include a team to use and I couldn\'t find one from this channel.', ephemeral=True
                )

        if role.id not in team['captain_roles']:
            return await interaction.response.send_message('This role is not a captain role on this team.', ephemeral=True)

        async with self.bot.safe_connection() as connection:
            await connection.execute(
                'UPDATE teams.settings SET captain_roles = array_remove(captain_roles, $1) WHERE id = $2',
                role.id,
                team['id'],
            )

        team['captain_roles'].remove(role.id)

        category = assertion(interaction.guild.get_channel(team['category_id']), Optional[discord.CategoryChannel])
        if category:
            overwrites = category.overwrites
            overwrites.pop(role, None)
            await category.edit(overwrites=overwrites, reason='Removing captain.')

        await self._sync_channels(interaction.guild, team['channels'])
        return await interaction.response.send_message(
            f'Removed {role.mention} from the {team["name"]} team.', ephemeral=True
        )


async def setup(bot: FuryBot) -> None:
    return await bot.add_cog(Teams(bot))
