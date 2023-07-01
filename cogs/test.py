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
from typing_extensions import Self, Unpack

from utils import panel
import discord
from discord.ext import commands
from typing import TYPE_CHECKING, Optional, Any

from utils import BaseCog, Context, BaseView
from utils.ui.view import BaseViewKwargs

if TYPE_CHECKING:
    from bot import FuryBot


@panel.register('test')
class Test:
    value: str
    channel_id: int = panel.field(
        type=panel.FieldType.CHANNEL_SELECT(channel_types=[discord.ChannelType.text]), display_name='Channel'
    )
    guild_id: int = panel.field(ignored=True)
    id: int = panel.field(ignored=True)
    bot: 'FuryBot' = panel.field(ignored=True)

    @property
    def guild(self) -> Optional[discord.Guild]:
        return self.bot.get_guild(self.guild_id)

    @property
    def channel(self) -> Optional[discord.TextChannel]:
        guild = self.guild
        if guild is None:
            return
        return guild.get_channel(self.channel_id)  # type: ignore


class _LaunchPanelView(BaseView):
    def __init__(self, panel_cls: panel.Panel[Any], instance: Any, **kwargs: Unpack[BaseViewKwargs]) -> None:
        super().__init__(**kwargs)
        self.panel_cls: panel.Panel[Any] = panel_cls
        self.instance: Any = instance

    @property
    def embed(self) -> discord.Embed:
        return discord.Embed(
            title='Launch Panel', description=f'Launch {self.panel_cls.__class__.__name__}?', color=discord.Color.blurple()
        )

    @discord.ui.button(label='Launch', style=discord.ButtonStyle.green)
    async def launch(
        self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]
    ) -> discord.InteractionMessage:
        await interaction.response.defer()
        view = self.panel_cls.create_underlying_view(self.instance, target=interaction, timeout=360)
        return await interaction.edit_original_response(view=view, embed=view.embed, content=None)


class TestCog(BaseCog):
    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name='test_panel')
    async def test_panel(self, ctx: Context) -> None:
        if TYPE_CHECKING:
            _LocalTestPanelCls: panel.Panel[Any]
        else:
            from cogs.test import Test as _LocalTestPanelCls

        instance_data = await ctx.bot.pool.fetchrow('SELECT * FROM test')
        assert instance_data

        async with ctx.typing():
            instance = Test(**dict(instance_data), bot=ctx.bot)
            view = _LaunchPanelView(panel_cls=_LocalTestPanelCls, instance=instance, target=ctx)
            await ctx.send("Launch with this button", view=view)


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(TestCog(bot))
