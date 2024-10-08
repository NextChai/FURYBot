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

import functools
from typing import TYPE_CHECKING, Any, List, Optional, Union, cast

import discord
from typing_extensions import Self, Unpack

from utils import (
    AfterModal,
    BaseView,
    BaseViewKwargs,
    MentionableSelect,
    SelectOneOfMany,
    UserSelect,
    default_button_doc_string,
)

from .practices.panel import PracticeMemberStatistics, TeamPracticesPanel
from .scrims.panel import TeamScrimsPanel
from .team import CaptainType, TeamMember

if TYPE_CHECKING:
    from bot import FuryBot

    from .team import Team


def clamp(minimum: Optional[int], maximum: int) -> int:
    if minimum is None:
        return maximum

    if minimum <= 0:
        return 1

    # Return the minimum if its less than or equal the maximum else the maximum.
    # If the minimum is 0 though, return 1 in replace of it.
    return minimum if minimum <= maximum else maximum


class TeamMemberView(BaseView):
    """A view used to manage a team member.

    Parameters
    Attributes
    ----------
    member: :class:`discord.Member`
        The member to manage.
    team: :class:`.Team`
        The team the member is in.
    """

    def __init__(self, member: Union[discord.Member, discord.User], team: Team, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.member: Union[discord.Member, discord.User] = member
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        embed = self.team.embed(title="Manage Team Member.", author=self.member)

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        embed.add_field(
            name="Is Sub?",
            value="Member is a sub." if team_member.is_sub else "Member is not a sub.",
        )

        return embed

    @discord.ui.button(label="Toggle Role")
    @default_button_doc_string
    async def toggle_role(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Swap the members role on the team. If they're on the main roster they'll be moved to a sub, and vice versa."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        coro = team_member.promote if team_member.is_sub else team_member.demote
        await coro()

        return await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Remove Member")
    @default_button_doc_string
    async def remove_member(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        """Remove this member from the team."""
        await interaction.response.defer()

        team_member = cast(TeamMember, self.team.get_member(self.member.id))
        await team_member.remove_from_team()

        view = TeamMembersView(self.team, target=interaction)
        return await interaction.edit_original_response(embed=view.embed, view=view)

    @discord.ui.button(label="View Practice Statistics")
    @default_button_doc_string
    async def view_practice_statistics(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """View the practice statistics for this member."""
        team_member = self.team.get_member(self.member.id)
        if not team_member:
            # This member has been removed while the view was open.
            return await interaction.response.send_message(
                "This member is not on the team. Were they removed?", ephemeral=True
            )

        view = self.create_child(PracticeMemberStatistics, team_member, self.member)
        await interaction.response.edit_message(view=view, embed=view.embed)


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

    def __init__(self, team: Team, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed for this view."""
        member_metadata: List[str] = []

        for member in self.team.team_members.values():
            member_metadata.append(f'{member.mention}: {"**Is a sub.**" if member.is_sub else "**On the main roster.**"}')

        embed = self.team.embed(
            title="Team Members",
            description="Use the buttons below to manage team members.\n\n{}".format(
                "\n".join(member_metadata) or "Team has no members."
            ),
        )

        return embed

    async def _manage_member_after(
        self,
        interaction: discord.Interaction[FuryBot],
        members: List[Union[discord.Member, discord.User]],
    ) -> None:
        await interaction.response.defer()

        member = members[0]

        team_member = self.team.get_member(member.id)
        if not team_member:
            await interaction.edit_original_response(embed=self.embed, view=self)
            return await interaction.followup.send("This member is not on the team.", ephemeral=True)

        view = self.create_child(TeamMemberView, member=member, team=self.team)
        await interaction.edit_original_response(embed=view.embed, view=view)

    @discord.ui.button(label="Manage Member")
    @default_button_doc_string
    async def manage_member(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Manage this member on the team. You can remove them from it and demote them to a sub."""
        UserSelect(after=self._manage_member_after, parent=self)
        return await interaction.response.edit_message(view=self)

    async def _manage_member_assignment(
        self,
        interaction: discord.Interaction[FuryBot],
        members: List[Union[discord.Member, discord.User]],
        *,
        assign_sub: bool = False,
        remove_member: bool = False,
    ) -> None:
        await interaction.response.defer()

        for member in members:
            if remove_member:
                team_member = self.team.get_member(member.id)
                if team_member is not None:
                    await self.team.remove_team_member(team_member)
            else:
                team_member = self.team.get_member(member.id)
                if team_member is None:
                    await self.team.add_team_member(member.id, is_sub=assign_sub)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Add Members")
    @default_button_doc_string
    async def add_members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Add members to this team."""
        UserSelect(after=self._manage_member_assignment, parent=self)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Remove Members")
    @default_button_doc_string
    async def remove_members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Remove members from this team."""
        UserSelect(
            after=functools.partial(self._manage_member_assignment, remove_member=True),
            parent=self,
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Add Subs")
    @default_button_doc_string
    async def add_subs(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Add subs to this team."""
        UserSelect(
            after=functools.partial(self._manage_member_assignment, assign_sub=True),
            parent=self,
        )

        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Remove Subs")
    @default_button_doc_string
    async def remove_subs(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Remove subs from this team."""
        UserSelect(
            after=functools.partial(self._manage_member_assignment, assign_sub=True, remove_member=True),
            parent=self,
        )
        return await interaction.response.edit_message(view=self)


class TeamChannelsView(BaseView):
    """A view used to manage and view team channels.

    Parameters
    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """discord.Embed: The embed for this view."""
        embed = self.team.embed(title="Channels.")

        category_channel = self.team.category_channel
        if category_channel:
            embed.add_field(name="Category Channel", value=category_channel.mention)

        text_channel = self.team.text_channel
        if text_channel:
            embed.add_field(name="Text Channel", value=text_channel.mention)

        voice_channel = self.team.voice_channel
        if voice_channel:
            embed.add_field(name="Voice Channel", value=voice_channel.mention)

        if self.team.extra_channels:
            embed.add_field(
                name="Extra Channels",
                value="\n".join([c.mention for c in self.team.extra_channels]) or "Team has no extra channels.",
            )

        return embed

    async def _create_extra_channel_after(
        self,
        interaction: discord.Interaction[FuryBot],
        channel_name_input: discord.ui.TextInput[AfterModal],
        channel_type_input: discord.ui.TextInput[AfterModal],
    ) -> discord.InteractionMessage:
        await interaction.response.defer()

        category_channel = self.team.category_channel
        if category_channel is None:
            return await interaction.edit_original_response(
                content="This team has no category channel to create the extra channel in.",
                view=self,
            )

        meth_mapping = {
            "text": category_channel.create_text_channel,
            "voice": category_channel.create_voice_channel,
        }

        meth = meth_mapping.get(channel_type_input.value)
        if meth:
            channel = await meth(name=channel_name_input.value)
            await self.team.add_extra_channel(channel.id)

        return await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label="Create Extra Channel")
    @default_button_doc_string
    async def create_extra_channel(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Allows the user to create an extra channel for the team."""
        modal = AfterModal(
            self.bot,
            self._create_extra_channel_after,
            discord.ui.TextInput(label="Channel Name", placeholder="Enter the channel name..."),
            discord.ui.TextInput(label="Channel Type", placeholder='"text" or "voice"...'),
            title="Create Extra Channel",
            timeout=None,
        )
        await interaction.response.send_modal(modal)

    async def _delete_extra_channels_after(self, interaction: discord.Interaction[FuryBot], values: List[str]) -> None:
        await interaction.response.defer()

        # Get the new channel ids
        valid_extra_channel_ids = self.team.extra_channel_ids.copy()

        for str_channel_id in values:
            channel_id = int(str_channel_id)
            if channel_id in valid_extra_channel_ids:
                valid_extra_channel_ids.remove(channel_id)

            channel = self.guild.get_channel(int(str_channel_id))
            if channel is not None:
                await channel.delete()

        await self.team.edit(extra_channel_ids=valid_extra_channel_ids)

        await interaction.edit_original_response(view=self, embed=self.embed)

    @discord.ui.button(label="Delete Extra Channels")
    @default_button_doc_string
    async def delete_extra_channel(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Allows the user to delete an extra channel for the team."""
        if not self.team.extra_channels:
            return await interaction.response.send_message("This team has no extra channels.", ephemeral=True)

        SelectOneOfMany(
            self,
            options=[
                discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in self.team.extra_channels
            ],
            after=self._delete_extra_channels_after,
            placeholder="Select the channels to delete...",
        )
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Sync Channels")
    @default_button_doc_string
    async def sync_channels(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Syncs the channels for the team."""
        await interaction.response.defer()
        await self.team.sync()
        await interaction.edit_original_response(embed=self.embed)


class TeamNamingView(BaseView):
    """A view used to manage naming and renaming a team.

    Parameters
    Attributes
    ----------
    team: :class:`.Team`
        The team to manage the scrims for.
    """

    def __init__(self, team: Team, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.team.embed(
            title="Customization",
            description=self.team.description or "Team has no description.",
        )
        embed.add_field(
            name="Team Nickname",
            value=self.team.nickname or "Team has no nickname.",
            inline=False,
        )

        if self.team.logo:
            embed.add_field(
                name="Team Logo",
                value=f"[Click here for logo.]({self.team.logo})." or "Team has no logo.",
                inline=False,
            )
        else:
            embed.add_field(name='Team Logo', value='Team has no logo.', inline=False)

        return embed

    async def _perform_after(
        self,
        interaction: discord.Interaction[FuryBot],
        text_input: discord.ui.TextInput[AfterModal],
        *,
        kwarg: str,
    ) -> None:
        await interaction.response.defer()

        await self.team.edit(**{kwarg: text_input.value})  # type: ignore

        # An edit, by itself, does not sync the team's actual text or voice channels.
        # Thus, when something like this does happen, the team must be synced to ensure
        # that the team chats are 1) up to date with the right names, and 2) Up to date with
        # the right permissions.
        await self.team.sync()

        await interaction.edit_original_response(embed=self.embed, view=self)

    async def _rename_after(
        self,
        interaction: discord.Interaction[FuryBot],
        text_input: discord.ui.TextInput[AfterModal],
    ) -> None:
        await self._perform_after(interaction, text_input, kwarg="name")

    async def _change_nickname_after(
        self,
        interaction: discord.Interaction[FuryBot],
        text_input: discord.ui.TextInput[AfterModal],
    ) -> None:
        await self._perform_after(interaction, text_input, kwarg="nickname")

    async def _change_description_after(
        self,
        interaction: discord.Interaction[FuryBot],
        text_input: discord.ui.TextInput[AfterModal],
    ) -> None:
        await self._perform_after(interaction, text_input, kwarg="description")

        text_channel = self.team.text_channel
        if text_channel:
            await text_channel.edit(topic=text_input.value)

    async def _change_logo_after(
        self,
        interaction: discord.Interaction[FuryBot],
        text_input: discord.ui.TextInput[AfterModal],
    ) -> None:
        await self._perform_after(interaction, text_input, kwarg="logo")

    @discord.ui.button(label="Rename")
    @default_button_doc_string
    async def rename(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Rename this team."""
        modal = AfterModal(
            self.bot,
            self._rename_after,
            discord.ui.TextInput(label="New Name", placeholder="Enter a new name...", max_length=100),
            title="Rename Team",
            timeout=None,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Change Nickname")
    @default_button_doc_string
    async def change_nickname(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Change the nickname of this team."""

        modal = AfterModal(
            self.bot,
            self._change_nickname_after,
            discord.ui.TextInput(
                label="New Nickname",
                placeholder="Enter a new nickname...",
                max_length=100,
            ),
            title="Change Team Nickname",
            timeout=None,
        )

        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Change Description")
    @default_button_doc_string
    async def change_description(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Change the description of this team."""
        modal = AfterModal(
            self.bot,
            self._change_description_after,
            discord.ui.TextInput(
                label="Update Description",
                placeholder="Enter a new description...",
                max_length=1024,
                required=False,
                style=discord.TextStyle.long,
            ),
            title="Change Team Description",
            timeout=None,
        )

        return await interaction.response.send_modal(modal)

    @discord.ui.button(label="Change Logo")
    @default_button_doc_string
    async def change_logo(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Change the logo of this team."""

        modal = AfterModal(
            self.bot,
            self._change_logo_after,
            discord.ui.TextInput(
                label="Update Logo",
                placeholder="Enter a new logo...",
                required=False,
                style=discord.TextStyle.short,
            ),
            title="Change Team Logo",
            timeout=None,
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

    def __init__(self, team: Team, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        embed = self.team.embed(
            title="Captains",
            description="Use the buttons below to manage team captains. This team "
            f"has **{len(self.team.captains)}** captain(s). A captain can be either "
            'a role or a user.',
        )
        embed.add_field(
            name="Current Captains",
            value="\n".join(r.mention for r in self.team.captains.values()) or "This team has no current captains.",
        )

        return embed

    async def handle_captain_action(
        self,
        interaction: discord.Interaction[FuryBot],
        targets: List[Union[discord.Role, discord.User, discord.Member]],
        *,
        add: bool = True,
    ) -> None:
        await interaction.response.defer()

        captain_types = {
            discord.Role: CaptainType.role,
            discord.User: CaptainType.user,
            discord.Member: CaptainType.user,
        }

        if add:
            for target in targets:
                await self.team.add_captain(target.id, captain_types[type(target)])
        else:
            for target in targets:
                await self.team.remove_captain(target.id)

        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Add Captains")
    @default_button_doc_string
    async def add_captain(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Add a captain role to this team."""
        MentionableSelect(self.handle_captain_action, self)
        return await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Remove Captains")
    @default_button_doc_string
    async def remove_captain(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Remove a captain role from this team."""
        MentionableSelect(functools.partial(self.handle_captain_action, add=False), self)
        return await interaction.response.edit_message(view=self)


class TeamView(BaseView):
    """The main Team View to edit a team.

    Parameters
    Attributes
    ----------
    team: :class:`Team`
        The team to display information for.
    """

    def __init__(self, team: Team, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.team: Team = team

    @property
    def embed(self) -> discord.Embed:
        """The embed for this view."""
        embed = self.team.embed(
            title=self.team.display_name,
            description=self.team.description or "Team has no description.",
        )

        embed.add_field(
            name="Members",
            value=", ".join([m.mention for m in self.team.team_members.values() if m.is_sub is False])
            or "Team has no members.",
            inline=False,
        )
        embed.add_field(
            name="Subs",
            value=", ".join([m.mention for m in self.team.team_members.values() if m.is_sub])
            or "Team has no dedicated subs.",
            inline=False,
        )

        embed.add_field(
            name="Captains",
            value=", ".join(r.mention for r in self.team.captains.values()) or "Team has no captains.",
            inline=False,
        )

        embed.add_field(
            name="Channels",
            value=", ".join(
                c.mention
                for c in [
                    self.team.text_channel,
                    self.team.voice_channel,
                    *self.team.extra_channels,
                ]
                if c is not None
            ),
            inline=False,
        )

        embed.set_footer(text=f"Team ID: {self.team.id}")
        return embed

    async def _delete_team_after(
        self,
        interaction: discord.Interaction[FuryBot],
        confirm_input: discord.ui.TextInput[AfterModal],
    ) -> None:
        if confirm_input.value.lower() != "delete":
            return await interaction.response.send_message("Aborted as `delete` was not typed.", ephemeral=True)

        await interaction.response.edit_message(content="This team has been deleted.", view=None, embed=None)

        async with self.bot.safe_connection() as connection:
            await self.team.delete(connection=connection, reason=f'Team deleted in team view by {interaction.user}')

    @discord.ui.button(label="Customization")
    @default_button_doc_string
    async def customization(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Launches the customization view for this team to rename it, change description, etc."""
        view = self.create_child(TeamNamingView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Channels")
    @default_button_doc_string
    async def channels(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s extra channels."""
        view = self.create_child(TeamChannelsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Scrims")
    @default_button_doc_string
    async def scrims(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Launches a view to manage the team\'s scrims."""
        view = self.create_child(TeamScrimsPanel, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Members")
    @default_button_doc_string
    async def members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s members."""
        view = self.create_child(TeamMembersView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Captains")
    @default_button_doc_string
    async def captains(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s captains."""
        view = self.create_child(TeamCaptainsView, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Practices")
    @default_button_doc_string
    async def practices(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Manage the team\'s practices."""
        view = self.create_child(TeamPracticesPanel, self.team)
        return await interaction.response.edit_message(embed=view.embed, view=view)

    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.danger)
    @default_button_doc_string
    async def delete(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """Delete this team."""
        modal = AfterModal(
            self.bot,
            self._delete_team_after,
            discord.ui.TextInput(
                label="Delete Team Confirmation",
                placeholder='Type "DELETE" to confirm...',
                max_length=6,
            ),
            title="Delete Team?",
            timeout=None,
        )

        return await interaction.response.send_modal(modal)
