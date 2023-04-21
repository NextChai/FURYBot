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
from typing import TYPE_CHECKING, Type
from typing_extensions import Self, Unpack

import discord

from utils import BaseView, BaseViewKwargs, default_button_doc_string, human_timestamp

from ...errors import TeamDeleted
from ..gameday import determine_comfy_sub_finding_times

if TYPE_CHECKING:
    from bot import FuryBot
    from ..gameday import Gameday
    from ...team import Team
    

class ConfirmSubFinding(BaseView):
    
    def __init__(self, gameday: Gameday, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        
        self.bot: FuryBot = gameday.bot
        self.gameday: Gameday = gameday
        
        team = gameday.team
        if team is None:
            raise TeamDeleted(team_id=gameday.team_id)
        
        self.team: Team = team
    
    @property
    def embed(self) -> discord.Embed:
        ...


class SubFinder(discord.ui.View):
    """The implementation of a given sub finder for a team's gameday.
    
    The sub finder will only have one button and an embed. Upon a given sub clicking
    the button, they will have to manually press another "Confirm" button that they can
    sub for the given team, time, and gameday. 
    
    This view does not dynamically find the data based on interaction data, so metadata
    needs to be passed in. This means, though, that the only instances of the :class:`SubFinder` should
    be active sub finders. Any **inactive** (completed) sub finders should be deleted.    
    
    
    Parameters
    ----------
    gameday: :class:`Gameday`
        The gameday that this sub finder is for.
    
    Attributes
    ----------
    gameday: :class:`Gameday`
        The gameday that this sub finder is for.
    team: :class:`Team`
        The team that this sub finder is for.
    bot: :class:`FuryBot`
        The bot instance.
    
    Raises
    ------
    TeamDeleted
        This team has been deleted but the sub finder was initialized.
    """
    def __init__(self, gameday: Gameday) -> None:
        self.bot: FuryBot = gameday.bot
        self.gameday: Gameday = gameday
        
        team = gameday.team
        if team is None:
            raise TeamDeleted(team_id=gameday.team_id)
        
        self.team: Team = team
        
    @property
    def embed(self) -> discord.Embed:
        embed = self.team.embed(
            title='Sub Needed',
            description=f'{self.gameday.subs_needed} sub(s) are needed for the upcoming gameday. '
            'This sub finder expires in {}'
        )
        
        embed.add_field(
            name='Gameday Starts At',
            value=human_timestamp(self.gameday.starts_at),
            inline=False
        )
        
        return embed
    
    @classmethod
    async def create(cls: Type[Self], *, gameday: Gameday, now: datetime.datetime) -> Self:
        bucket = gameday.bucket
        if bucket is None:
           raise ValueError('Cannot create a sub finder for a gameday that has no bucket.')
       
        sub_finding_channel = bucket.automatic_sub_finding_channel
        if sub_finding_channel is None:
            raise ValueError('Cannot create a sub finder for a gameday that has no sub finding channel.')
        
        comfy_sub_fiding_times = determine_comfy_sub_finding_times(starts_at=gameday.starts_at, now=now)
        if not comfy_sub_fiding_times.can_use_automatic_sub_finding:
            # TODO: Better error here
            raise ValueError('Cannot create a sub finder for a gameday that is too close to start.')
    
        self = cls(gameday=gameday)
        message = await sub_finding_channel.send(view=self, embed=self.embed)
        
        # Let's create a timer for when the sub finder should end
        bot = gameday.bot
        timer_id = discord.utils.MISSING
        if bot.timer_manager:
            timer = await bot.timer_manager.create_timer(
                comfy_sub_fiding_times.end,
                'sub_finding_timer_end',
                guild_id=gameday.guild_id,
                team_id=gameday.team_id,
                gameday_id=gameday.id,
                sub_finding_message_id=message.id
            )    
            timer_id = timer.id    
        
        async with bot.safe_connection() as connection:
            await gameday.edit(
                connection=connection,
                sub_finder_starts_at=comfy_sub_fiding_times.start,
                sub_finder_ends_at=comfy_sub_fiding_times.end,
                sub_finder_timer_id=timer_id
            )
            
        return self


    @discord.ui.button(label='I Can Attend', style=discord.ButtonStyle.green)
    @default_button_doc_string
    async def can_attend(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> discord.InteractionMessage:
        """A button pressed by a user whenn they want to sub for the given gameday. This will launch a confirm view."""
        await interaction.response.defer(ephemeral=True)
        
        view = ConfirmSubFinding(gameday=self.gameday, target=interaction)
        return await interaction.edit_original_response(view=view, embed=view.embed)