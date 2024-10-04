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

import datetime
from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Union

import discord
from typing_extensions import Self

from utils import BaseView, Context

from .grabber import SentenceGrabber

if TYPE_CHECKING:
    from bot import FuryBot

MISSING = discord.utils.MISSING


# Implementation of levenshtein distance between two sentences. Returns the distance between the two sentences as a float.
def levenshtein_distance(s1: str, s2: str) -> float:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def typing_accuracy(user_sentence: str, original_sentence: str) -> float:
    distance = levenshtein_distance(user_sentence, original_sentence)
    return 1 - abs(distance / len(original_sentence))


def words_per_minute(sentence: str, time: float) -> float:
    words = len(sentence.split())
    return (words / time) * 60


class TTPacket(NamedTuple):
    member_id: int
    sentence: str
    started_typing_at: datetime.datetime


class TypingTestView(BaseView):
    def __init__(self, ctx: Context) -> None:
        super().__init__(target=ctx, timeout=5 * 60)

        self.channel = ctx.channel
        self.message: discord.Message = MISSING

        self.packets: Dict[int, TTPacket] = {}
        self.grabber: SentenceGrabber = SentenceGrabber(filename="assets/text/shrek_script.txt", min_sentence_length=10)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title='Test Your Typing Speed',
            description='Press "Start!" to begin a typing test! Once you click it, I\'ll '
            'send you a sentence to type out. Anyone can participate, but you can only try to '
            'type one sentence at a time!',
        )

        embed.add_field(
            name='Timeout Warning',
            value='This typing test will time out after 5 minutes of inactivity. '
            'When it does, the Start button will become unusable.',
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot]) -> bool:
        if self.packets.get(interaction.user.id):
            await interaction.response.send_message(
                "You\'re already in a typing test! You cannot start two at one time!", ephemeral=True
            )
            return False

        return True

    async def on_timeout(self) -> None:
        self.start.disabled = True

        if self.message is not MISSING:
            await self.message.edit(view=self)

    async def _watch_for_message(self, author: Union[discord.User, discord.Member]) -> Optional[discord.Message]:
        def check(message: discord.Message) -> bool:
            if not message.content:
                return False

            if message.channel != self.channel:
                return False

            if author != message.author:
                return False

            if not message.guild:
                return False

            packet = self.packets.get(message.author.id)
            return bool(packet)

        message = await self.bot.wait_for('message', check=check, timeout=60 * 5)

        packet = self.packets.get(message.author.id)
        if not packet:
            raise ValueError("Packet is missing, this should not happen.")

        guild = message.guild
        if not guild:
            raise ValueError("Guild is not available in guild only command.")

        async with self.channel.typing():
            accuracy = typing_accuracy(message.content, packet.sentence)

            # If we were less than 60% accurate, we don't count it
            ratio_too_large = accuracy < 0.6
            if ratio_too_large:
                return await message.reply(f"Woah there! You only got the sentence {(accuracy * 100):.2f}% correct...")

            # Remove their packet from the cache
            self.packets.pop(message.author.id, None)

            total_time = (message.created_at - packet.started_typing_at).total_seconds()
            wpm = words_per_minute(packet.sentence, total_time)
            await message.reply(
                f"You typed the sentence in `{total_time:.2f} seconds` with an accuracy of `{(accuracy * 100):.2f}%`. That\'s `{wpm:.2f} WPM`!"
            )

    @discord.ui.button(label='Start!', style=discord.ButtonStyle.green)
    async def start(self, interaction: discord.Interaction[FuryBot], button: discord.ui.Button[Self]) -> None:
        await interaction.response.defer(ephemeral=True)

        async with self.grabber:
            sentence = self.grabber.grab()

        packet = TTPacket(member_id=interaction.user.id, sentence=sentence, started_typing_at=interaction.created_at)
        self.packets[interaction.user.id] = packet

        embed = self.bot.Embed(author=interaction.user, description=sentence)
        await interaction.followup.send(embed=embed)

        self.bot.create_task(self._watch_for_message(interaction.user))
