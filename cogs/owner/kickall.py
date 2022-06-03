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

import string
import random
import asyncio
from typing import TYPE_CHECKING, List, Tuple
from typing_extensions import Self

import discord
from discord.ext import commands

from utils import BaseCog
from utils.context import Context
from utils.constants import (
    BLOB_BAN,
    BLOB_SEENSOMESTUFF,
    BLOB_PAIN,
    NOT_LIKE_BLOB,
    BLOB_UPSET,
    BLOB_WEARY,
    GENERAL_CHANNEL,
    COACH_ROLE,
    MOD_ROLE,
    CAPTAIN_ROLE,
    BYPASS_FURY,
    GAME_CONSULTANT_ROLE,
    REMOVE,
    CHECK,
    ROO_LOVE,
    FURY,
    ROO_DEVIL,
)

if TYPE_CHECKING:
    from bot import FuryBot

ALLOWED_MENTIONS: discord.AllowedMentions = discord.AllowedMentions.all()
BLOB_EMOJIS: Tuple[str, ...] = (BLOB_BAN, BLOB_SEENSOMESTUFF, BLOB_PAIN, NOT_LIKE_BLOB, BLOB_UPSET, BLOB_WEARY)
KICK_REASONS: Tuple[str, ...] = (
    '$mention was kicked!',
    '$mention found a magical coin, and upon touching it got kicked!',
    'This party is McDonalds, I\'m lovin it! $mention ate too many big macs and got kicked!',
    'I asked $mention what their favorite color was. It was wrong. They\'ve been kicked.',
    '$mention trained for years to be a ninja, just to get kicked!',
    '$mention decided to split up and search for clues. It seems they got lost!',
    '$mention sneezed on his keyboard and got kicked!',
    '$mention found out what happens to a soccer ball today.',
    'We apoligise, but; the caller you are trying to reach is currently unavailable. $mention has been kicked.',
    '$mention looked at the shape of Italy today, a boot!',
    '$mention made like Dora\'s sidekick today, Boots!',
    'I lost connection with $mention in the tunnel!',
    '$mention got escorted to the hospital for a checkup. It turns out they were fine but got kicked instead!',
    '$mention held the L for too long and got kicked!',
    '$mention, :clown:',
    '$mention was kicked by a clown!',
    'Another one bites the dust! $mention has been removed!',
    '$mention couldn\'t find his keys and got lost!',
    '$mention, L bozo!',
    '$mention found Sparta today.',
)


class FinalWords(discord.ui.View):
    """A view that allows the user to enter in any final words, if any.
    We'll use :meth:`wait` in the command callback to wait for the user to
    send something, and then we'll KICK THEM.
    
    This class inherits :class:`~discord.ui.View` and has a timeout of 20 seconds.
    
    Paramters
    ---------
    bot: :class:`FuryBot`
        The bot instance.
    channel: :class:`discord.TextChannel`
        The channel used to send messges to, this is the #general channel.
    member: :class:`discord.Member`
        The member to request information from.
        
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot instance.
    channel: :class:`discord.TextChannel`
        The channel used to send messges to, this is the #general channel.
    member: :class:`discord.Member`
        The member to request information from.
    button_pressed: :class:`bool`
        Whether or not the user pressed a button. We'll use this in the :meth:`on_timeout` function.
    """
    
    if TYPE_CHECKING:
        message: discord.Message

    def __init__(self, bot: FuryBot, channel: discord.TextChannel, member: discord.Member) -> None:
        self.bot: FuryBot = bot
        self.channel: discord.TextChannel = channel
        self.member: discord.Member = member
        self.button_pressed: bool = False
        super().__init__(timeout=20)

    def disable_children(self) -> None:
        """A method to disable all the children of the view."""
        for child in self.children:
            assert isinstance(child, discord.ui.Button)
            child.disabled = True

    async def on_timeout(self) -> None:
        """|coro|
        
        A method called when the view times out. If the user didn't press a button,
        then we'll make the channel known, but if they do then delete the message.
        """
        if not self.button_pressed:
            await self.message.edit(
                embed=self.bot.Embed(
                    title='Quiet, huh?',
                    description=f'{self.member.mention} chose not to press a button {BLOB_PAIN}',
                    author=self.member,
                ),
                view=None,
            )
        else:
            await self.message.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """|coro|
        
        A method to check if the user that pressed the button is the same as the member that is supposed to be kicked.
        
        Parameters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the button press.
        
        Returns
        -------
        :class:`bool`
            Whether or not the user is authorized to press the button.
        """
        check = interaction.user == self.member
        if not check:
            await interaction.response.send_message('Hey, this isn\'t yours!', ephemeral=True)

        return check

    @discord.ui.button(
        label='Yes I have final words', style=discord.ButtonStyle.green, emoji=discord.PartialEmoji.from_str(CHECK)
    )
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """|coro|
        
        Called when the "yes" button has been pressed by the member that is supposed to be kicked. This
        callback will allow the user to send their final words to the channel.
        
        Parmaeters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the button press.
        button: :class:`discord.ui.Button`
            The button that was pressed.
        """
        self.button_pressed = True
        self.disable_children()

        embed = self.bot.Embed(
            title=f'{self.member.display_name}, Final Words Eh?',
            description=f'{self.member.mention}, you have **60 seconds to say your final words**.',
            author=self.member,
        )

        await interaction.response.edit_message(embed=embed, view=self, allowed_mentions=ALLOWED_MENTIONS)
        await self.channel.set_permissions(self.member, send_messages=True)

        try:
            message: discord.Message = await self.bot.wait_for(
                'message', check=lambda m: m.author == self.member, timeout=60
            )
        except asyncio.TimeoutError:
            embed = self.bot.Embed(
                title='Nothing to Say?', description=f'{self.member.mention} couldn\'t type fast enough lmao, :clown:'
            )
            await interaction.edit_original_message(embed=embed, view=None, allowed_mentions=ALLOWED_MENTIONS)
            return self.stop()

        embed = self.bot.Embed(
            title=f'Final Words From {self.member.display_name}', description=message.content, author=self.member
        )
        try:
            await interaction.edit_original_message(embed=embed)
        except (discord.HTTPException, discord.NotFound):
            pass

        # NOTE: REMOVE THE TRY EXCEPT
        try:
            await message.add_reaction(discord.PartialEmoji.from_str(ROO_LOVE))
        except:
            pass

        await asyncio.sleep(2)

    @discord.ui.button(
        label='I do not have final words.', style=discord.ButtonStyle.danger, emoji=discord.PartialEmoji.from_str(REMOVE)
    )
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button[Self]) -> None:
        """|coro|
        
        Called when the "no" button has been pressed by the member that is supposed to be kicked. This
        callback will alert the channel that the user chose to not have final words.
        
        Parmaeters
        ----------
        interaction: :class:`discord.Interaction`
            The interaction that was created from the button press.
        button: :class:`discord.ui.Button`
            The button that was pressed.
        """
        self.button_pressed = True
        self.disable_children()

        embed = self.bot.Embed(title=f'{self.member.mention} chose not to say any final words.', description=BLOB_PAIN)
        await interaction.response.edit_message(embed=embed, view=self, allowed_mentions=ALLOWED_MENTIONS)
        self.stop()


class Kickall(BaseCog):
    @staticmethod
    def fifty_fifty() -> bool:
        """:class:`bool`: A random ``True`` or ``False`` based upon a coin flip."""
        return random.random() >= 0.5
    
    def thank_you_embed(self, member: discord.Member) -> discord.Embed:
        """A method used to return a simple thank you embed sent to the user that was kicked.
        
        Parameters
        ----------  
        member: :class:`discord.Member`
            The member that was kicked.
        
        Returns
        -------
        :class:`discord.Embed`
            The embed that will be sent to the user.
        """
        return self.bot.Embed(
            title='Thank you!',
            description=f'From all of us at the **Fury** team, thank you for joining in our season of **Fury**! Through this season we have been able to grow our community and we hope to see you in the next one! {FURY}',
            author=member,
        )
    
    async def fetch_members(self, ctx: Context) -> List[discord.Member]:
        """|coro|
        
        Fetch all members within the guild and remove the ones that should not be kicked.
        
        Parameters
        ----------
        ctx: :class:`Context`
            The context of the command.
        
        Returns
        -------
        List[:class:`discord.Member`]
            A list of all members within the guild that should be kicked.
        """
        assert ctx.guild is not None
        
        members: List[discord.Member] = [
            member
            async for member in ctx.guild.fetch_members(limit=None)
            if not member.bot and member.top_role < ctx.guild.me.top_role
        ]

        # We need to make sure special members arent included in the list
        role_ids: List[int] = [COACH_ROLE, MOD_ROLE, CAPTAIN_ROLE, BYPASS_FURY, GAME_CONSULTANT_ROLE]
        for role_id in role_ids:
            role = ctx.guild.get_role(role_id)
            if role is None:
                continue

            role_members = role.members
            for member in role_members:
                if member in members:
                    members.remove(member)

        random.shuffle(members)
        return members
    
    async def prompt_kick(self, general: discord.TextChannel, member: discord.Member) -> None:
        """|coro|
        
        A method used to prompt the user that they're going to be kicked. This will alert the user it's their turn,
        allow them to say some final words, send them a nice message, then kick them.
        
        Parameters
        ----------
        general: :class:`discord.TextChannel`
            The general chat channel.
        member: :class:`discord.Member`
            The member that is going to be kicked.
        """
        # Alert the user that it's their turn
        embed = self.bot.Embed(
            title=f'{member.display_name}, it\'s time!',
            description=f'{member.mention}, do you have any final words? You have **20** seconds to press **Yes** or **No**.',
        )

        # Create our view and send our message to the general channel
        final_words = FinalWords(self.bot, general, member)
        final_words.message = await general.send(embed=embed, view=final_words, allowed_mentions=ALLOWED_MENTIONS)
        
        # Wait for the view to be done.
        await final_words.wait()

        # Send the thank you message to the member
        await self.bot.send_to(member, embed=self.thank_you_embed(member))

        try:
            # Kick the member
            await member.kick(reason='Enjoy your summer, see you soon!')
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            # Ope! The member left before we could kick them
            message = await general.send(
                f'It seems {member.mention} has left the server before I could kick them lmao :clown:'
            )
        else:
            # Create a kick message
            kick_message = string.Template(random.choice(KICK_REASONS)).safe_substitute(mention=member.mention)

            # Maybe add an emoji?
            if self.fifty_fifty():
                kick_message += f' {random.choice(BLOB_EMOJIS)}'

            # Send it to the channel
            message = await general.send(kick_message)

        await asyncio.sleep(3)
        await message.edit(
            content=message.content
            + '\n\n**The next member will be chosen in 30 seconds.** Feel free to chat among yourselves.'
        )

    @commands.command(name='kickall', description='Kick everyone in the server', brief='BAHAHA')
    @commands.guild_only()
    async def kickall(self, ctx: Context) -> None:
        """|coro|
        
        Used to kick every unauthorized member from the FLVS Fury Discord server. This will
        go through every member, give them some time to say goodbyes, and then remove them.
        """
        assert ctx.guild is not None

        # Let's get some confirmation from the invoker
        value = await ctx.get_confirmation(
            embed=self.bot.Embed(
                title='Are you sure?',
                description='This will start the kicking process for **every** member in the server.\n\n**This action can not be undone.**',
            )
        )
        if not value:
            return

        if ctx.channel.id == GENERAL_CHANNEL:
            general = ctx.channel  # type: ignore # This is a known type
        else:
            general: discord.TextChannel = ctx.guild.get_channel(GENERAL_CHANNEL)  # type: ignore # This is a known type

            # NOTE: REMOVE ME
            if general is None:
                general = ctx.channel  # type: ignore

        # This could take a while, so let's make sure the user knows what's going on
        embed = self.bot.Embed(
            title='The kicking process has been started!',
            description='This might take a little bit to collect all of the data needed, so hold tight!',
        )
        embed.add_field(
            name='How is this going to work?',
            value='FuryBot will pick someone at random, give them time to say final words, then kick them!',
            inline=False,
        )

        message: discord.Message = await general.send(embed=embed)

        async with ctx.typing():
            members = await self.fetch_members(ctx)

        # Let's alert the spectators
        embed = self.bot.Embed(
            title='ITS TIME',
            description=f'Starting the kicking process in **30 seconds**... {ROO_DEVIL}',
        )
        embed.add_field(name='Total members to kick', value=f'{len(members)} total.', inline=False)

        await message.edit(embed=embed)
        await asyncio.sleep(30)

        for member in members:
            await general.set_permissions(ctx.guild.default_role, send_messages=False)

            await self.prompt_kick(general, member)

            await general.set_permissions(ctx.guild.default_role, send_messages=True)
            await asyncio.sleep(30)

        await general.send('Everyone has been kicked :sob:')
