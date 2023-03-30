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

from typing import TYPE_CHECKING, Dict, List, NamedTuple

import discord
from typing_extensions import Self, Unpack

from utils import BaseView, MultiSelector, AfterModal

from .gameday import Gameday, GamedayBucket, GamedayMember, GamedayTime

if TYPE_CHECKING:
    from bot import FuryBot
    from utils import BaseViewKwargs

GamedayMemberInformation = NamedTuple('GamedayMemberInformation', [('gameday', GamedayMember), ('discord', discord.Member)])


class SelectGameday(MultiSelector['GamedayBucketPanel', 'Gameday']):
    def __init__(self, *, parent: GamedayBucketPanel) -> None:
        super().__init__(
            parent=parent,
            items=list(parent.bucket.get_gamedays()),
            per_page=5,
            modal_title='Choose Gameday',
            modal_item=discord.ui.TextInput(
                label='Enter Gameday ID',
                placeholder='Enter the Gameday ID you chose from the embed.',
            ),
        )

    def create_embed(self, gamedays: List[Gameday]) -> discord.Embed:
        team = self.parent.bucket.team
        assert team  # We can not get here without a team

        embed = team.embed(
            title=f'Select A Gameday',
            description='Use the "Choose Gameday" button to type in the ID of the gameday you want to manage.',
        )

        now = discord.utils.utcnow()
        for gameday in gamedays:
            metadata: List[str] = [f'`ID`: {gameday.id}']

            verbage = 'Starts At' if gameday.starts_at > now else 'Started At'
            metadata.append(
                f'`{verbage}`: {discord.utils.format_dt(gameday.starts_at, "F")} ({discord.utils.format_dt(gameday.starts_at, "R")})'
            )

            if gameday.ended_at is not None:
                metadata.append(
                    f'`Ended At`: {discord.utils.format_dt(gameday.ended_at, "F")} ({discord.utils.format_dt(gameday.ended_at, "R")})'
                )
            else:
                metadata.append('`Status`: Gameday has not ended.')

            # Add some info about the members playing
            mentions: List[str] = []
            for member in gameday.get_members():
                if member.is_attending:
                    mentions.append(member.mention)
                else:
                    mentions.append(f'~~{member.mention}~~')

            if mentions:
                metadata.append(f'`Members`: {", ".join(mentions)}')

            embed.add_field(name=f'Gameday {gameday.id}', value='\n'.join(metadata), inline=False)

        return embed

    def hash_item(self, gameday: Gameday) -> str:
        return str(gameday.id)

    async def on_item_chosen(self, interaction: discord.Interaction[FuryBot], item: Gameday) -> None:
        view = self.parent.create_child(GamedayPanel, gameday=item)
        return await interaction.response.edit_message(view=view, embed=view.embed)


class SelectGamedayTime(MultiSelector['GamedayTimeManagementPanel', 'GamedayTime']):
    def __init__(self, *, parent: GamedayTimeManagementPanel):
        super().__init__(
            parent=parent,
            items=list(parent.gameday_times.values()),
            per_page=10,
            modal_title='Choose Gameday Time',
            modal_item=discord.ui.TextInput(
                label='Enter Gameday Time ID',
                placeholder='Enter the Gameday Time ID you chose from the embed.',
            ),
        )

    def create_embed(self, gamedays: List[GamedayTime]) -> discord.Embed:
        ...

    def hash_item(self, gameday: GamedayTime) -> str:
        return str(gameday.id)

    async def on_item_chosen(self, interaction: discord.Interaction[FuryBot], item: GamedayTime) -> None:
        ...


class GamedayMemberPanel(BaseView):
    def __init__(self, member: GamedayMember, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.member: GamedayMember = member

    @property
    def embed(self) -> discord.Embed:
        ...

    @discord.ui.button(label='Toggle Is Temporary Sub')
    async def toggle_is_temporary_sub(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        ...

    @discord.ui.button(label='Remove Member From Gameday')
    async def remove_member_from_gameday(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        ...


class GamedayPanel(BaseView):
    def __init__(self, gameday: Gameday, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.gameday = gameday

    @property
    def embed(self) -> discord.Embed:
        ...

    @discord.ui.button(label='Manage Members')
    async def manage_members(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='Skip This Gameday (bye week)')
    async def skip_gameday(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='Manage Images')
    async def manage_images(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...


class ManageGamedayTime(BaseView):
    def __init__(self, gameday_time: GamedayTime, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.gameday_time = gameday_time

    @property
    def embed(self) -> discord.Embed:
        ...

    @discord.ui.button(label='Edit Gameday Time and Weekday', style=discord.ButtonStyle.green)
    async def edit_gameday_time(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...

    @discord.ui.button(label='Delete Gameday Time', style=discord.ButtonStyle.red)
    async def delete_gameday_time(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...


class GamedayTimeManagementPanel(BaseView):
    def __init__(self, bucket: GamedayBucket, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.bucket: GamedayBucket = bucket
        self.gameday_times: Dict[int, GamedayTime] = bucket.gameday_times

    @property
    def embed(self) -> discord.Embed:
        team = self.bucket.team
        if team is None:
            raise ValueError('Gameday bucket has no team.')

        embed = team.embed(title=f'Game Time Management')

        for gameday_time in self.gameday_times.values():
            ...

    async def _create_new_gametime_after(
        self, interaction: discord.Interaction, weekday_time_input: discord.ui.TextInput[AfterModal]
    ) -> discord.InteractionMessage:
        ...

    @discord.ui.button(label='Create New Gameday Time', style=discord.ButtonStyle.green)
    async def create_new_gameday_time(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        ...

    @discord.ui.button(label='Manage Existing Gameday Time')
    async def manage_existing_gameday_time(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        selector = SelectGamedayTime(parent=self)
        await selector.launch(interaction)


class GamedayBucketPanel(BaseView):
    """Represents the view panel for a given gameday bucket. This will allow the user to edit
    it's settings and view it's current settings.

    Parameters
    Attributes
    ----------
    bucket: :class:`GamedayBucket`
        The bucket that this panel is for.
    """

    def __init__(self, bucket: GamedayBucket, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.bucket = bucket

    @property
    def embed(self) -> discord.Embed:
        team = self.bucket.team
        if team is None:
            raise ValueError('The bucket must have a team to create an embed.')

        embed = team.embed(
            title=f'{team.display_name} Bucket Management',
            description='Use the buttons below to manage this bucket.',
        )

        embed.add_field(
            name='Gameday Times',
            value='\n'.join(
                f'{gametime.weekday.name.title()}s at {gametime.starts_at.strftime("%I:%M.%S %p")}'
                for gametime in self.bucket.gameday_times.values()
            )
            or 'No gameday times have been set for this bucket.',
            inline=False,
        )

        automatic_sub_channel_fmt: str
        automatic_sub_finding_channel = self.bucket.automatic_sub_finding_channel

        if automatic_sub_finding_channel is not None:
            automatic_sub_channel_fmt = f'{automatic_sub_finding_channel.mention} is used to find subs for this bucket.'
        else:
            if self.bucket.automatic_sub_finding_channel_id is not None:
                automatic_sub_channel_fmt = (
                    'I could not find the channel to use for automatic sub finding. Did it get deleted?'
                )
            else:
                automatic_sub_channel_fmt = 'There is no channel set for automatic sub finding.'

        embed.add_field(name='Automatic Sub Finding Channel', value=automatic_sub_channel_fmt, inline=False)

        embed.add_field(
            name='Automatic Sub Finding',
            value=f'Automatic sub finding when possible is **{"enabled" if self.bucket.automatic_sub_finding_if_possible else "disabled"}**. '
            'Note that, at times, it is not possible to use automatic sub finding. This is only because a moderator has changed a gameday\'s '
            'settings 24 hours before the gameday.',
            inline=False,
        )

        return embed

    @discord.ui.button(label='Manage Gameday Times', style=discord.ButtonStyle.green)
    async def manage_gameday_times(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        await interaction.response.defer()

        view = self.create_child(GamedayTimeManagementPanel, bucket=self.bucket)

        return await interaction.response.edit_message(view=view, embed=view.embed)

    @discord.ui.button(label='Manage A Gameday', style=discord.ButtonStyle.primary)
    async def manage_a_gameday(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        """A button to launch a view that manages all gamedays in this bucket."""
        selector = SelectGameday(parent=self)
        await selector.launch(interaction)
