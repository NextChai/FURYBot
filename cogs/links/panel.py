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

import discord
from typing_extensions import Unpack, Self

from utils import BaseView, BaseViewKwargs, human_timedelta

from .settings import *


class CreateLinkSettings(BaseView):
    def __init__(self, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(title='Create Link Filtering')
        embed.add_field(
            name='What is Link Filtering?',
            value='It is effortless for members to post inappropriate links in a standard Discord server, '
            'but have no fear because Link Filtering is here! With link filtering, you can limit all links '
            'sent to your Discord server and only allow specific links/domains. This ensures all content being '
            'posted to your Discord server is PG for a school environment.',
            inline=False,
        )

        embed.add_field(
            name='How do I Setup Link Filtering?',
            value='Press the "Create Link Filtering" button below and the bot will prepare everything! '
            'From there, you can choose which links/domains you want to be allowed and the '
            'consequences of a member posting an unauthorized link. ',
            inline=False,
        )

        embed.add_field(
            name='Can I Delete Link FIltering After It\'s Created?',
            value='Absolutely! If you create a link filter and then, later on, decide you want to remove it, '
            'that is totally ok! A "Delete" button has been provided for you.',
            inline=False,
        )

        return embed

    @discord.ui.button(label='Create Link Filtering', style=discord.ButtonStyle.green)
    async def create_link_filtering(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        ...


class ManageLinkActions(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        ...


class ManageAllowedTargets(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        ...


class ManageLinkSettings(BaseView):
    def __init__(self, settings: LinkSettings, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.settings: LinkSettings = settings

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Link Filtering Settings', description='Use the buttons below to manage your link filtering settings.'
        )

        # Let's get the current ctions and words from these settings.
        embed.add_field(
            name='Allowed Targets',
            value=f'There is **{len(self.settings.allowed_links)}** allowed '
            'targets for link filtering. Click the button below to manage them.',
            inline=False,
        )

        actions_display: List[str] = []
        for action in self.settings.actions:
            if action.type is LinkActionType.mute:
                assert action.delta
                actions_display.append(f'╰ Mute author for {human_timedelta(action.delta.total_seconds())}')
            elif action.type is LinkActionType.surpress:
                actions_display.append('╰ Surpress (delete) the message.')
            elif action.type is LinkActionType.warn:
                actions_display.append(f'╰ Warn the author: "{action.warn_message}"')

        actions = f'On a link sent to your Discord server, the bot will take the following action(s):\n'
        if actions_display:
            actions += "\n".join(actions_display)
        else:
            actions += "╰ No actions will be taken."

        embed.add_field(
            name='Actions',
            value=actions,
            inline=False,
        )

        return embed

    @discord.ui.button(label='Manage Allowed Targets')
    async def manage_allowed_targets(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> None:
        ...

    @discord.ui.button(label='Manage Actions')
    async def manage_actions(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        ...
