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
from typing import TYPE_CHECKING, Any, Callable, Coroutine, List, Optional, TypeVar, cast

import discord
from typing_extensions import Self, Unpack

from cogs.teams.scrim.persistent import AwayConfirm, HomeConfirm
from utils import CHANNEL_EMOJI_MAPPING, AutoRemoveSelect, BaseView, BaseViewKwargs, BasicInputModal, TimeTransformer

from .scrim import ScrimStatus
from .team import TeamMember

if TYPE_CHECKING:
    from .scrim import Scrim
    from .team import Team

BV = TypeVar('BV', bound='BaseView')
ButtonCallback = Callable[[BV, discord.Interaction, discord.ui.Button[BV]], Coroutine[Any, Any, Any]]


def clamp(minimum: int, maximum: int) -> int:
    # Return the minimum if its less than or equal the maximum else the maximum
    return minimum if minimum <= maximum else maximum


def _default_button_doc_string(func: ButtonCallback[BV]) -> ButtonCallback[BV]:
    default_doc = """
    |coro|
    
    {doc}
    
    Parameters
    ----------
    interaction: :class:`discord.Interaction`
        The interaction that triggered this button.
    button: :class:`discord.ui.Button`
        The button that was clicked.
    """
    func.__doc__ = default_doc.format(doc=func.__doc__ or '')
    return func


class TeamMemberView(BaseView):
    """A view used to manage a team member.

    Parameters
    ----------
    member: :class:`.TeamMember`
        The member to manage.

    Attributes
    ----------
    :class:`.TeamMember`
        The member to manage.
    """

    def __init__(self, member: discord.Member, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.member: discord.Member = member
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.bot.Embed(title=f'Manage Team {self.team.name} Member.')

        embed.set_author(name=self.member.display_name, icon_url=self.member.display_avatar.url)
        embed.set_thumbnail(url=self.member.display_avatar.url)

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        embed.add_field(name='Is Sub?', value='Member is a sub.' if team_member.is_sub else 'Member is not a sub.')

        return embed

    @discord.ui.button(label='Toggle Role')
    @_default_button_doc_string
    async def toggle_role(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Swap the members role on the team. If they're on the main roster they'll be moved to a sub, and vice versa."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        coro = team_member.promote if team_member.is_sub else team_member.demote
        await coro()

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Remove Member')
    @_default_button_doc_string
    async def remove_member(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Remove this member from the team."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        await team_member.remove_from_team()

        view = TeamMembersView(self.team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)


class TeamMembersView(BaseView):
    """A view used to manage team members.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        member_metadata: List[str] = []

        for member in self.team.team_members.values():
            member_metadata.append(f'{member.mention}: {"Is Sub" if member.is_sub else "Is Not Sub"}')

        embed = self.bot.Embed(
            title=f'Team {self.team.name} Members',
            description='Use the buttons below to manage team members.\n\n{}'.format(
                "\n".join(member_metadata or ['Team has no members.'])
            ),
        )
        embed.set_author(name=self.team.name, icon_url=self.team.logo)
        embed.set_thumbnail(url=self.team.logo)

        return embed

    async def _manage_member_after(self, select: discord.ui.UserSelect[Self], interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        team_member = self.team.get_member(select.values[0])
        if not team_member:
            await interaction.edit_original_response(embed=self.embed, view=self)
            await interaction.followup.send('This member is not on the team.', ephemeral=True)
            return

        member = cast(discord.Member, select.values[0])
        view = self.create_child(TeamMemberView, member=member, team=self.team)
        await interaction.edit_original_response(embed=view.embed, view=view)

    async def _manage_member_assignment(
        self,
        select: discord.ui.UserSelect[Self],
        interaction: discord.Interaction,
        *,
        assign_sub: bool = False,
        remove_member: bool = False,
    ) -> None:
        await interaction.response.defer()

        for member in select.values:
            if remove_member:
                team_member = self.team.get_member(member.id)
                if team_member is not None:
                    await self.team.remove_team_member(team_member)
            else:
                team_member = self.team.get_member(member.id)
                if team_member is None:
                    await self.team.add_team_member(member.id, is_sub=assign_sub)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Manage Member')
    @_default_button_doc_string
    async def manage_member(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage this member on the team. You can remove them from it and demote them to a sub."""
        AutoRemoveSelect(item=discord.ui.UserSelect[Self](), parent=self, callback=self._manage_member_after)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Add Members')
    @_default_button_doc_string
    async def add_members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add members to this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to add...'
            ),
            parent=self,
            callback=self._manage_member_assignment,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Members')
    @_default_button_doc_string
    async def remove_members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove members from this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to add...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, remove_member=True),
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Add Subs')
    @_default_button_doc_string
    async def add_subs(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add subs to this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to add...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, assign_sub=True),
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Subs')
    @_default_button_doc_string
    async def remove_subs(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove subs from this team."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to add...'
            ),
            parent=self,
            callback=functools.partial(self._manage_member_assignment, remove_member=True),
        )
        return await interaction.response.edit_message(view=self)


class ScrimView(BaseView):
    """Represents a view used to manage a scrim.

    Parameters
    ----------
    team: :class:`.Team`
        The team currently being viewed in the view history.
    scrim: :class:`.Scrim`
        The scrim to manage.

    Attributes
    ----------
    team: :class:`.Team`
        The team currently being viewed in the view history.
    scrim: :class:`.Scrim`
        The scrim to manage.
    """

    def __init__(self, team: Team, scrim: Scrim, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        self.scrim: Scrim = scrim
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.bot.Embed(
            title='Team Scrim Information',
            description=f'This scrim is scheduled for {self.scrim.scheduled_for_formatted()}',
        )
        embed.add_field(
            name='Home Team',
            value=f'{self.scrim.home_team.name}\n**Confirmed Members**: {", ".join([m.mention for m in self.scrim.home_voters] or ["No home voters."])}',
            inline=False,
        )
        embed.add_field(
            name='Away Team',
            value=f'{self.scrim.away_team.name}\n**Confirmed Members**: {", ".join([m.mention for m in self.scrim.away_voters] or ["No away voters."])}',
        )
        embed.add_field(name='Status', value=self.scrim.status.value.title())

        embed.set_author(name=self.scrim.home_team.name, icon_url=self.scrim.home_team.logo)
        embed.set_thumbnail(url=self.scrim.home_team.logo)

        embed.set_footer(text=f'Scrim ID: {self.scrim.id}')
        return embed

    async def _reschedule_scrim_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        # Let's try and parse this time
        value = modal.children[0].value
        try:
            transformed = await TimeTransformer('n/a').transform(interaction, value)
        except Exception as exc:
            await interaction.edit_original_response(embed=self.embed, view=self)
            return await interaction.followup.send(content=str(exc), ephemeral=True)

        assert transformed.dt
        await self.scrim.reschedle(transformed.dt, editor=interaction.user)
        await interaction.edit_original_response(
            content=f'I\'ve rescheduled this scrim for {self.scrim.scheduled_for_formatted()}.'
        )

    async def _manage_member_assignment(
        self, select: discord.ui.UserSelect[Self], interaction: discord.Interaction, *, add_vote: bool = True
    ) -> None:
        await interaction.response.defer()

        home_team = self.scrim.home_team
        away_team = self.scrim.away_team

        for member in select.values:
            home_member = home_team.get_member(member.id)
            team = home_team if home_member is not None else away_team

            if add_vote:
                await self.scrim.add_vote(member.id, team.id)
            else:
                await self.scrim.remove_vote(member.id, team.id)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Reschedule')
    @_default_button_doc_string
    async def reschedule_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Reschedule this scrim to a later date."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(self.bot, after=self._reschedule_scrim_after)
        modal.add_item(
            discord.ui.TextInput(label='When you want to reschedule this scrim to. For example: Tomorrow at 4pm.')
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Remove Confirmation')
    @_default_button_doc_string
    async def remove_confirmation(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Forcefully remove confirmation for a member."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to remove confirmation for...'
            ),
            callback=functools.partial(self._manage_member_assignment, add_vote=False),
            parent=self,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Add Confirmation')
    @_default_button_doc_string
    async def force_add_confirmation(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Forcefully add confirmation for a member."""
        AutoRemoveSelect(
            item=discord.ui.UserSelect[Self](
                max_values=clamp(self.guild.member_count, 25), placeholder='Select members to remove confirmation for...'
            ),
            callback=self._manage_member_assignment,
            parent=self,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Force Schedule Scrim')
    @_default_button_doc_string
    async def force_schedule_scrim(
        self, interaction: discord.Interaction, button: discord.ui.Button[Self]
    ) -> Optional[discord.InteractionMessage]:
        """Forcefully set the scrim\'s status to :attr:`.ScrimStatus.scheduled`. This can not be done if the home team hasn't confirmed."""
        if not self.scrim.away_message_id:
            return await interaction.response.send_message(
                'You can not force start a scrim that has not been confirmed by the home team.', ephemeral=True
            )

        await interaction.response.defer()

        await self.scrim.change_status(ScrimStatus.scheduled)

        # Update the home message
        home_message = await self.scrim.home_message()
        view = HomeConfirm(self.scrim)
        await home_message.edit(embed=view.embed, view=None)

        # Update the away message
        away_message = await self.scrim.away_message()
        if away_message:
            view = AwayConfirm(self.scrim)
            await away_message.edit(embed=view.embed, view=None)

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Cancel Scrim', style=discord.ButtonStyle.danger)
    @_default_button_doc_string
    async def cancel_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Force cancel the scrim and remove it from the database."""
        await interaction.response.defer()
        await self.scrim.cancel()

        # Go back to the TeamScrimsView, the parent of this view, and edit the original response.
        # We can't go back in the parent tree because I dont want the user to try and edit
        # a cancelled scrim.
        view = TeamScrimsView(self.team, target=self.target)
        await interaction.edit_original_response(embed=view.embed, view=view)


class TeamScrimsView(BaseView):
    """A view used to manage a teams scrims, alter times, etc.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.bot.Embed(title=f"{self.team.name}'s Scrims")

        hosted_scrims: int = 0
        for scrim in self.team.scrims:
            if scrim.home_team == self.team:
                hosted_scrims += 1

            embed.add_field(
                name=f'Scrim {discord.utils.format_dt(scrim.scheduled_for, "R")}',
                value=f'**Team Created Scrim**: {scrim.home_team.name}\n'
                f'**Away Team**: {scrim.away_team.name}\n'
                f'**Status**: {scrim.status.value.title()}'
                f'**Home Team Confirmed**: {", ".join([m.mention for m in scrim.home_voters] or ["No home votes."])}\n'
                f'**Away Team Confirmed**: {", ".join([m.mention for m in scrim.away_voters] or ["No away votes."])}\n',
            )

        embed.description = (
            f'**{self.team.name}** has {len(self.team.scrims)} scrims total, '
            f'**{hosted_scrims}** of which they are hosting.'
        )

        if hosted_scrims == 0:
            embed.add_field(name='No Scrims', value='This team has no scrims.')

        embed.set_author(name=self.team.name, icon_url=self.team.logo)
        embed.set_thumbnail(url=self.team.logo)

        return embed

    async def _manage_a_scrim_callback(self, select: discord.ui.Select[Any], interaction: discord.Interaction) -> None:
        scrim = discord.utils.get(self.team.scrims, id=int(select.values[0]))
        if not scrim:
            # Something really went wrong!
            return await interaction.response.edit_message(embed=self.embed, view=self)

        view = ScrimView(self.team, scrim, target=self.target)
        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Select a Scrim')
    @_default_button_doc_string
    async def manage_a_scrim(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to select a scrim to manage."""
        if not self.team.scrims:
            return await interaction.response.send_message('This team has no scrims.', ephemeral=True)

        AutoRemoveSelect(
            item=discord.ui.Select[Self](
                placeholder='Select a scrim to manage...',
                options=[
                    discord.SelectOption(
                        label=scrim.scheduled_for.strftime("%A, %B %d, %Y at %I:%M %p"),
                        value=str(scrim.id),
                    )
                    for scrim in self.team.scrims
                ],
            ),
            parent=self,
            callback=self._manage_a_scrim_callback,
        )

        # The AutoRemoveSelect automatically removes all children
        # and adds itslef. Once the select has been completed it will
        # add the children back and call the "_manage_a_scrim_callback" callback for us.
        return await interaction.response.edit_message(view=self)


class TeamChannelsView(BaseView):
    """A view used to manage and view team channels.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """discord.Embed: The embed for this view."""
        embed = self.bot.Embed(title=f'{self.team.name} Channels.')
        embed.set_author(name=self.team.name, icon_url=self.team.logo)
        embed.set_thumbnail(url=self.team.logo)

        embed.add_field(name='Category Channel', value=self.team.category_channel.mention)
        embed.add_field(name='Text Channel', value=self.team.text_channel.mention)
        embed.add_field(name='Voice Channel', value=self.team.voice_channel.mention)
        embed.add_field(
            name='Extra Channels',
            value='\n'.join([c.mention for c in self.team.extra_channels] or ['Team has no extra channels.']),
        )

        return embed

    async def _create_extra_channel_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any], discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        channel_name: str = modal.children[0].value
        channel_type: str = modal.children[1].value

        meth_mapping = {
            'text': self.team.category_channel.create_text_channel,
            'voice': self.team.category_channel.create_voice_channel,
        }

        meth = meth_mapping.get(channel_type.lower(), None)
        if meth:
            channel = await meth(name=channel_name)

            extra_channel_ids = self.team.extra_channel_ids.copy()
            extra_channel_ids.append(channel.id)
            await self.team.edit(extra_channel_ids=extra_channel_ids)

        await interaction.edit_original_response(view=self, embed=self.embed)

    async def _delete_extra_channels_after(self, select: discord.ui.Select[Self], interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        # Get the new channel ids
        valid_extra_channel_ids = self.team.extra_channel_ids.copy()

        for str_channel_id in select.values:
            channel_id = int(str_channel_id)
            if channel_id in valid_extra_channel_ids:
                valid_extra_channel_ids.remove(channel_id)

            channel = self.guild.get_channel(int(str_channel_id))
            if channel is not None:
                await channel.delete()

        await self.team.edit(extra_channel_ids=valid_extra_channel_ids)

        await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label='Create Extra Channel')
    @_default_button_doc_string
    async def create_extra_channel(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to create an extra channel for the team."""
        modal: BasicInputModal[discord.ui.TextInput[Any], discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot,
            after=self._create_extra_channel_after,
            title='Create Extra Channel',
            timeout=None,
        )
        modal.add_item(discord.ui.TextInput(label='Channel Name', placeholder='Enter the channel name...'))
        modal.add_item(discord.ui.TextInput(label='Channel Type', placeholder='"text" or "voice"...'))
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Delete Extra Channels')
    @_default_button_doc_string
    async def delete_extra_channel(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Allows the user to delete an extra channel for the team."""
        if not self.team.extra_channels:
            return await interaction.response.send_message('This team has no extra channels.', ephemeral=True)

        AutoRemoveSelect(
            item=discord.ui.Select[Self](
                max_values=clamp(len(self.team.extra_channel_ids), 25),
                placeholder='Select the channels to delete...',
                options=[
                    discord.SelectOption(
                        label=channel.name, value=str(channel.id), emoji=CHANNEL_EMOJI_MAPPING.get(type(channel), None)
                    )
                    for channel in self.team.extra_channels
                ],
            ),
            parent=self,
            callback=self._delete_extra_channels_after,
        )

        return await interaction.response.edit_message(view=self)


class TeamNamingView(BaseView):
    """A view used to manage naming and renaming a team.


    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.bot.Embed(
            title=f'{self.team.name} Customization', description=self.team.description or 'Team has no description.'
        )
        embed.set_author(name=self.team.name, icon_url=self.team.logo, url=self.team.logo)
        embed.add_field(name='Team Nickname', value=self.team.nickname or 'Team has no nickname.', inline=False)
        embed.add_field(
            name='Team Logo', value=f'[Click here for logo.]({self.team.logo}).' or 'Team has no logo.', inline=False
        )

        if self.team.logo:
            embed.set_thumbnail(url=self.team.logo)

        return embed

    async def _perform_after(
        self, kwarg_name: str, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer()

        value = modal.children[0].value
        await self.team.edit(**{kwarg_name: value})
        await interaction.edit_original_response(embed=self.embed, view=self)

    async def _rename_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after("name", modal, interaction)

    async def _change_nickname_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after("nickname", modal, interaction)

    async def _change_description_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self._perform_after('description', modal, interaction)

    async def _change_logo_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        await self.perform_after('logo', modal, interaction)

    @discord.ui.button(label='Rename')
    @_default_button_doc_string
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Rename this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Rename Team', after=self._rename_after
        )
        modal.add_item(discord.ui.TextInput(label='New Name', placeholder='Enter a new name...', max_length=100))
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Nickname')
    @_default_button_doc_string
    async def change_nickname(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the nickname of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Nickname', after=self._change_nickname_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Nickname', placeholder='Enter a new nickname...', max_length=100, required=False
            )
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='Change Description')
    @_default_button_doc_string
    async def change_description(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the description of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Nickname', after=self._change_description_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Description',
                placeholder='Enter a new description...',
                max_length=1024,
                required=False,
                style=discord.TextStyle.long,
            )
        )
        await interaction.response.send_modal(modal)

        await modal.wait()
        await self.team.text_channel.edit(topic=modal.children[0].value)

    @discord.ui.button(label='Change Logo')
    @_default_button_doc_string
    async def change_logo(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Change the logo of this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, title='Change Team Logo', after=self._change_description_after
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Update Logo',
                placeholder='Enter a new logo...',
                required=False,
                style=discord.TextStyle.short,
            )
        )
        await interaction.response.send_modal(modal)


class TeamCaptainsView(BaseView):
    """A view used to manage the captains of a team.

    Parameters
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.

    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, *args: Any, **kwargs: Any) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        captain_fmt = '\n'.join(r.mention for r in self.team.captain_roles)
        embed = self.bot.Embed(
            title=f'{self.team.name} Captains',
            description='Use the buttons below to manage team captain roles. This team '
            f'has **{len(captain_fmt)}** captain(s).\n\n{captain_fmt}',
        )

        return embed

    async def handle_captain_action(
        self, select: discord.ui.RoleSelect[Self], interaction: discord.Interaction, *, add: bool = True
    ) -> None:
        await interaction.response.defer()

        meth = self.team.add_captain if add else self.team.remove_captain
        for role in select.values:
            await meth(role.id)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label='Add Captains')
    @_default_button_doc_string
    async def add_captain(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Add a captain role to this team."""
        AutoRemoveSelect(
            item=discord.ui.RoleSelect[Self](max_values=clamp(len(self.team.captain_roles), 25)),
            parent=self,
            callback=self.handle_captain_action,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Remove Captains')
    @_default_button_doc_string
    async def remove_captain(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Remove a captain role from this team."""
        AutoRemoveSelect(
            item=discord.ui.RoleSelect[Self](max_values=clamp(len(self.team.captain_roles), 25)),
            parent=self,
            callback=functools.partial(self.handle_captain_action, add=False),
        )
        return await interaction.response.edit_message(view=self)


class TeamView(BaseView):
    """The main Team View to edit a team."""

    def __init__(self, team: Team, *args: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        self.team: Team = team
        super().__init__(*args, **kwargs)

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.bot.Embed(
            title=self.team.name,
            description=self.team.description or 'Team has no description.',
        )

        embed.set_author(name=self.team.name, icon_url=self.team.logo)

        if self.team.logo is not None:
            embed.set_thumbnail(url=self.team.logo)

        if self.team.nickname is not None:
            embed.add_field(name='Team Nickname', value=self.team.nickname or 'Team has no nickname.', inline=False)

        embed.add_field(
            name='Team Members',
            value=', '.join(
                [m.mention for m in self.team.team_members.values() if m.is_sub is False] or ['Team has no members.']
            ),
        )
        embed.add_field(
            name='Team Subs',
            value=', '.join(
                [m.mention for m in self.team.team_members.values() if m.is_sub is False] or ['Team has no members.']
            ),
        )

        embed.add_field(
            name='Team Channels',
            value='\n'.join(
                c.mention
                for c in [
                    self.team.text_channel,
                    self.team.voice_channel,
                    self.team.category_channel,
                    *self.team.extra_channels,
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name='Team Captains', value='\n'.join([r.mention for r in self.team.captain_roles] or ['Team has no captains.'])
        )

        embed.set_footer(text=f'Team ID: {self.team.id}')
        return embed

    async def _delete_team_after(
        self, modal: BasicInputModal[discord.ui.TextInput[Any]], interaction: discord.Interaction
    ) -> None:
        value = modal.children[0].value

        if value.lower() != 'delete':
            return await interaction.response.send_message('Aborted as `delete` was not typed.', ephemeral=True)

        await self.team.delete()
        return await interaction.response.edit_message(content='This team has been deleted.', view=None, embed=None)

    @discord.ui.button(label='Customization')
    @_default_button_doc_string
    async def customization(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches the customization view for this team to rename it, change description, etc."""
        view = self.create_child(TeamNamingView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Channels')
    @_default_button_doc_string
    async def channels(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s extra channels."""
        view = self.create_child(TeamChannelsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Scrims')
    @_default_button_doc_string
    async def scrims(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s scrims."""
        view = self.create_child(TeamScrimsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Members')
    @_default_button_doc_string
    async def members(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s members."""
        view = self.create_child(TeamMembersView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Captains')
    @_default_button_doc_string
    async def captains(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s captains."""
        view = self.create_child(TeamCaptainsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label='Delete Team', style=discord.ButtonStyle.danger)
    @_default_button_doc_string
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """Delete this team."""
        modal: BasicInputModal[discord.ui.TextInput[Any]] = BasicInputModal(
            self.bot, after=self._delete_team_after, title='Delete Team?'
        )
        modal.add_item(
            discord.ui.TextInput(
                label='Delete Team Confirmation',
                placeholder='Type "DELETE" to confirm...',
                max_length=6,
            )
        )
        return await interaction.response.send_modal(modal)
