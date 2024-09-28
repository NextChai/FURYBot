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

from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import discord
from typing_extensions import Self

from cogs.teams.errors import MemberNotOnTeam
from cogs.teams.practices.errors import MemberAlreadyInPractice
from utils import default_button_doc_string, human_timedelta

if TYPE_CHECKING:
    from bot import FuryBot

    from .practice import Practice, PracticeMember

__all__: Tuple[str, ...] = ("PracticeView", "UnableToAttendModal")


class UnableToAttendModal(discord.ui.Modal):
    """A modal spawned from the :class:`PracticeView` when a member opts-out of a practice.

    Parameters
    ----------
    practice: :class:`Practice`
        The practice that the member is opting out of.
    member: :class:`discord.Member`
        The member that is opting out of the practice.
    """

    reason: discord.ui.TextInput[Self] = discord.ui.TextInput(
        label="Why Can't You Attend?",
        style=discord.TextStyle.long,
        custom_id="reason-to-not-attend",
        placeholder="Enter why you can't attend. This will not be shared with any of your team members.",
        required=True,
    )

    def __init__(self, *, practice: Practice, member: Union[discord.Member, discord.User]) -> None:
        self.practice: Practice = practice
        self.member: Union[discord.Member, discord.User] = member
        super().__init__(timeout=None, title="Why Can't You Attend?")

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        """|coro|

        A check to ensure that the interaction is from the member that is opting out of the practice.
        """
        if interaction.user != self.member:
            return await interaction.response.send_message("Hey! This isn't yours!", ephemeral=True)

        return True

    async def on_submit(self, interaction: discord.Interaction[FuryBot], /) -> None:
        """|coro|

        Called when the modal has been submitted. Will handle the member opting out of the practice
        and complain to the invoker if they're not on the team or they've already opted out.

        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction created from the user pressing "Submit".
        """
        await interaction.response.defer()

        try:
            await self.practice.handle_member_unable_to_join(member=self.member, reason=self.reason.value)
        except MemberNotOnTeam:
            return await interaction.followup.send("Hey! You aren't on this team, you can't do this!", ephemeral=True)
        except MemberAlreadyInPractice:
            return await interaction.followup.send(
                "Hey! You are already registered to be in this practice. "
                "If you can't attend leave your teams voice channel and it'll be marked accordingly.",
                ephemeral=True,
            )

        await interaction.followup.send(
            "Thanks for letting me know, I've made a mark on your record.",
            ephemeral=True,
        )


class PracticeView(discord.ui.View):
    """The persistent practice view creates when a practice is created.

    Parameters
    ----------
    practice: :class:`Practice`
        The practice that the persistent view is being created for.
    """

    def __init__(self, practice: Practice) -> None:
        self.practice: Practice = practice
        super().__init__(timeout=None)

    @property
    def _practice_done_embed(self) -> discord.Embed:
        team = self.practice.team
        started_by = self.practice.started_by

        if not team:
            # This team has been deleted while the user is still in the practice.
            return self.practice.bot.Embed(
                title="Team Deleted!",
                description="This team has been deleted while this panel is active.",
                color=discord.Color.red(),
            )

        attending_member_mentions: List[str] = [member.mention for member in self.practice.attending_members]
        excused_member_mentions: List[str] = [member.mention for member in self.practice.excused_members]
        members_unattended_mentions: List[str] = [member.mention for member in self.practice.missing_members]

        embed = team.embed(
            title=f"{team.display_name} Practice.",
            description=f"A practice started by {started_by and started_by.mention or '`<not found>`'} on {self.practice.format_start_time()} is currently in progress has come to an end.",
        )

        # Show the members that attended the practice.
        embed.add_field(
            name="Members Attended",
            value="\n".join(attending_member_mentions),
            inline=False,
        )

        if excused_member_mentions:
            embed.add_field(
                name="Excused Members",
                value="\n".join(excused_member_mentions),
                inline=False,
            )

        if members_unattended_mentions:
            embed.add_field(
                name="Members Unattended",
                value="\n".join(members_unattended_mentions),
                inline=False,
            )

        total_time = self.practice.get_total_practice_time()
        if total_time:
            embed.add_field(
                name="Total Practice Time",
                value=f"In total, **todays practice was {human_timedelta(total_time.total_seconds())}**. More stats have been posted "
                "in the practice completed message.",
            )

        return embed

    @property
    def embed(self) -> discord.Embed:
        """:class:`discord.Embed`: The embed that is displayed in the persistent view for this practice."""
        if not self.practice.ongoing:
            return self._practice_done_embed

        team = self.practice.team
        started_by = self.practice.started_by

        if not team:
            # This has been deleted while the user is still in the practice.
            return self.practice.bot.Embed(
                title="Team Deleted!",
                description="This team has been deleted while this panel is active.",
                color=discord.Color.red(),
            )

        embed = team.embed(
            title=f"{team.display_name} Practice.",
            description=f"A practice started by {started_by and started_by.mention or '`<not-found>`'} on {self.practice.format_start_time()} "
            "is currently in progress.",
        )

        voice_channel = team.voice_channel
        if not voice_channel:
            # This team's main voice channel has been deleted WHILE the practice is ongoing.
            embed.add_field(
                name="Woah there cowboy!",
                value="This team's text channel has been deleted while the practice is ongoing. "
                "Contact an admin to fix this issue.",
                inline=False,
            )
            embed.color = discord.Color.red()
            return embed

        embed.add_field(name="Voice Channel", value=voice_channel.mention, inline=False)

        attending_members: List[PracticeMember] = []
        unable_to_attend: List[PracticeMember] = []
        for member in self.practice.members:
            if not member.attending:
                unable_to_attend.append(member)
            else:
                attending_members.append(member)

        embed.add_field(
            name="Attending Members",
            value="\n".join([member.mention for member in attending_members]),
            inline=False,
        )

        if unable_to_attend:
            embed.add_field(
                name="Unable to Attend",
                value="\n".join([member.mention for member in unable_to_attend]),
                inline=False,
            )

        embed.add_field(
            name="How Do I Attend?",
            value=f"**To attend your team practice, join your team's voice channel, {voice_channel.mention}. "
            "Your team practice time will be recorded once you leave the voice channel.**",
            inline=False,
        )

        embed.add_field(
            name="I Can't Attend!",
            value="Press the \"I Can't Attend\" button below to let us know why you can't attend. "
            "This will be recorded on your attendance record.",
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> bool:
        # If this practice has ended, the user should not be able to interact with it.
        if self.practice.ongoing:
            return True

        await interaction.response.send_message(
            "This practice has ended, you can no longer interact with it.", ephemeral=True
        )
        return False

    async def update_message(self) -> None:
        """|coro|

        Updates the message this persistent view is attached to with the updated embed.

        This is called whenever a practice member joins or leaves a voice channel.
        """
        team_text_channel = self.practice.team and self.practice.team.text_channel
        if not team_text_channel:
            # This team text channel has been deleted, we cannot update anything
            return

        message_id = self.practice.message_id
        message = await team_text_channel.fetch_message(message_id)
        await message.edit(view=self, embed=self.embed)

    @discord.ui.button(
        label="I Can't Attend",
        style=discord.ButtonStyle.red,
        custom_id="unable-to-attend",
    )
    @default_button_doc_string
    async def handle_unable_to_attend(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        """Called when the user presses the "I Can't Attend" button.". Will spawn the unable to attend modal."""
        await interaction.response.send_modal(UnableToAttendModal(practice=self.practice, member=interaction.user))
