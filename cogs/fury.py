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
import collections

import asyncio
import textwrap
import random
from typing import TYPE_CHECKING, List, Optional, Set

import discord
from discord.ext import commands

from utils import BaseCog, Context, human_join

if TYPE_CHECKING:
    from bot import FuryBot

VOTING_TIME: int = 8
GRACE_PERIOD: int = 7

LEAD_CAPTAIN_ROLE_ID: int = 763384816942448640
CAPTAIN_ROLE_ID: int = 765360488816967722
BOTS_ROLE_ID: int = 763455351332798485

KICKENING_MESSAGES: List[str] = [
    "Oops! Looks like you got kicked! Better luck next time, champ.",
    "Kicked out of the game and the server? Ouch, that's gotta hurt.",
    "Time to take a break and rethink your strategy. Kicked!",
    "Don't worry, it's just a kick in the pants. See you soon!",
    "You've been kicked to the curb. Better dust off your gaming skills.",
    "A kick in the server is worth two in the game. Time to regroup.",
    "Kicked and banished! Time to work on those team skills.",
    "Kicked to the sidelines? Use this time to practice and come back stronger.",
    "Kicked out? That's okay, there's always room for improvement.",
    "Kicked, but not defeated! Keep pushing for that victory.",
    "Sorry, but you're not living up to the game's standards. Kicked!",
    "Kicked like a ball in Rocket League. Keep your head up!",
    "No need to rage quit, you've already been kicked. Come back stronger.",
    "The only way to go is up after getting kicked. Good luck!",
    "Kicked for being a sore loser? Try being a gracious winner instead.",
    "Kicked, but still loved. Come back and join the fun again soon!",
    "A kick in the server is a wake-up call. Time to up your game!",
    "You can't win them all, but you can learn from getting kicked. Keep going!",
    "Looks like you've been kicked from the game. Time to Overwatch your strategy.",
    "Mario Kart outta here! You've been kicked from the server.",
    "Sorry, but you're not Smash-ing it today. You've been kicked!",
    "Kicked like a soccer ball in Rocket League? Time to work on your defense.",
    "We're not Spla-toon with you today. You've been kicked from the game.",
    "You've been kicked from the server. That's a Valo-rant, don't you think?",
    "League of Legends? More like League of Losers. You've been kicked!",
    "Kicked from the server? It's time to Get-Gooder at the game.",
    "Sorry, you're not living up to our standards. You've been Overwatch-ed and kicked.",
    "Kicked from the server? Looks like you need to Aimbot-ter next time.",
    "Super Smash Bros? More like Super Smashed by the ban hammer. You've been kicked!",
    "Mario Karted out of the server. Time to re-Luigi-n your gaming skills.",
    "Splatoon? More like Sploosh-gone. You've been kicked!",
    "Kicked from the server? That's not very VALOR-ant of us.",
    "Time to take a break and re-focus. You've been kicked from the game.",
    "Sorry, we had to kick you out. We don't want any toxicity in our community.",
    "Kicked from the server? It's time to level up your gaming skills.",
    "Looks like you're not quite ready for the big leagues. You've been kicked.",
    "We're not seeing eye-to-eye on this one. You've been kicked from the game.",
    "Kicked from the server? Don't worry, there's always next time.",
    "Sorry, but you're not on our team today. You've been kicked from the game.",
    "Kicked from the server? Time to re-strategize and come back stronger.",
    "Looks like we need to recalibrate. You've been kicked from the game.",
    "Kicked from the server? Don't take it personally, it's just business.",
    "Sorry, but you've been voted off the island. You've been kicked from the server.",
    "Looks like it's game over for you. You've been kicked from the server.",
    "Kicked from the server? Take this as a sign to practice and improve your skills.",
    "Sorry, but you're just not cutting it. You've been kicked from the game.",
    "Kicked from the server? We don't tolerate cheaters in our community.",
    "Looks like it's time for a time out. You've been kicked from the game.",
    "Sorry, but we had to give you the boot. Your puns were too cheesy.",
    "Kicked from the server? Looks like you'll have to find another way to procrastinate.",
    "Looks like your gameplay needs a reboot. You've been kicked from the game.",
    "Kicked from the server? Don't worry, we won't hold it against you... much.",
    "Sorry, but you're just not winning us over. You've been kicked from the game.",
    "Kicked from the server? It's time to switch up your strategy.",
    "Looks like you need to take a breather. You've been kicked from the game.",
    "Kicked from the server? Don't sweat it, we've all been there before... but I haven't!",
    "Sorry, but you're not quite our cup of tea. You've been kicked from the server.",
    "Kicked from the server? We had to make room for our pet hamster. Sorry!",
    "Looks like it's time for a reality check. You've been kicked from the game.",
    "Kicked from the server? Maybe you should try playing with your eyes open next time.",
    "Sorry, but you're just not keeping up with the pack. You've been kicked from the game.",
    "Kicked from the server? We have a strict 'no camping' policy.",
    "Looks like it's time for a reboot. You've been kicked from the game.",
]


def should_kick_member(member: discord.Member) -> bool:
    member_role_ids = [role.id for role in member.roles]

    if any(
        (
            LEAD_CAPTAIN_ROLE_ID in member_role_ids,
            CAPTAIN_ROLE_ID in member_role_ids,
            BOTS_ROLE_ID in member_role_ids,
        )
    ):
        return False

    me = member.guild.me
    if member.top_role >= me.top_role:
        return False

    return True


class KickeningMemberButton(discord.ui.Button['KickeningView']):
    def __init__(self, parent: KickeningView, member: discord.Member) -> None:
        super().__init__(label=textwrap.shorten(member.display_name, width=80), style=discord.ButtonStyle.red)
        self.parent = parent
        self.member = member

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        await interaction.response.defer()  # The client's latency will skyrocket, this is precautionary

        async with self.parent.lock:
            self.parent.voting_counter[self.member] += 1
            self.parent.voted_members.add(interaction.user.id)

            # Edit with the new count
            await interaction.edit_original_response(view=self.parent, embed=self.parent.embed)

        await interaction.followup.send('Your vote has been counted!', ephemeral=True)


class KickeningView(discord.ui.View):
    def __init__(self, bot: FuryBot, voting_members: List[discord.Member]) -> None:
        super().__init__(timeout=VOTING_TIME)
        self.bot = bot

        self.kickening_members: List[discord.Member] = voting_members
        self.voting_counter: collections.Counter[discord.Member] = collections.Counter(self.kickening_members)
        self.lock: asyncio.Lock = asyncio.Lock()

        self.voted_members: Set[int] = set()

        for member in self.kickening_members:
            self.add_item(KickeningMemberButton(self, member))

    @property
    def embed(self) -> discord.Embed:
        first = self.kickening_members[0]
        second = self.kickening_members[1]

        embed = self.bot.Embed(
            title=textwrap.shorten(f'{first.display_name} vs {second.display_name}', 256),
            description='Use the buttons below to vote for who you want to kick! This is an anonymous vote.',
        )

        embed.add_field(name=first.display_name, value=f'**{self.voting_counter[first]} votes**.')
        embed.add_field(name=second.display_name, value=f'**{self.voting_counter[second]} votes**.')

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        if interaction.user in self.kickening_members:
            return await interaction.response.send_message(
                'You cannot vote when you\'re up for the kickening!', ephemeral=True
            )

        if interaction.user.id in self.voted_members:
            return await interaction.response.send_message('You have already voted!', ephemeral=True)

        return True


class FurySpecificCommands(BaseCog):
    @commands.command(name='start_kickening', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def start_kickening(self, ctx: Context) -> None:
        """Starts the kickening."""
        assert ctx.guild

        all_kickable_members: List[discord.Member] = []
        offline_members: List[discord.Member] = []
        async with ctx.typing():
            async for member in ctx.guild.fetch_members(limit=None):
                if not should_kick_member(member):
                    continue

                if member.status is discord.Status.offline:
                    offline_members.append(member)
                    continue

                all_kickable_members.append(member)

        random.shuffle(all_kickable_members)

        await ctx.send(
            embed=self.bot.Embed(
                title='Fetched All Members',
                description=f'Fetched {len(all_kickable_members)} members for the kickening, let it begin!',
            ),
            delete_after=3,
        )

        for offline_member in offline_members:
            await ctx.send(
                embed=self.bot.Embed(
                    title=f'{offline_member.display_name} is offline!',
                    description=f'{offline_member.mention} is offline on Discord, so they will not be included in the kickening. Someone '
                    'didn\'t look at <#757666199214751794>! Shame on them, bye bye!',
                ),
                delete_after=3,
                content=offline_member.mention,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            # await offline_member.kick(reason='Offline member')
            await ctx.send(random.choice(KICKENING_MESSAGES))

        # We're going to use a while True loop here and abuse some mutable objects
        while True:
            # Spawn a new view
            kickable_members = random.choices(all_kickable_members, k=2)

            view = KickeningView(self.bot, kickable_members)
            message = await ctx.channel.send(
                embed=view.embed,
                view=view,
                content=human_join((m.mention for m in kickable_members)),
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            await view.wait()

            async with ctx.typing():
                await message.edit(view=None)

                # Now we can get the results of the vote
                voting_results = view.voting_counter.most_common(2)
                first_member, first_votes = voting_results[0]
                second_member, second_votes = voting_results[1]

                if first_votes == second_votes:
                    # This is a tie, randomize the winner
                    member_to_kick = random.choice(voting_results)[0]
                else:
                    member_to_kick = first_member if first_votes > second_votes else second_member

                embed = self.bot.Embed(
                    title=textwrap.shorten(f'Results Of {first_member.display_name} vs {second_member.display_name}', 256),
                    description=f'I\'m sorry {member_to_kick.mention}, but your time has come! You will be kicked!',
                )

                embed.add_field(name=first_member.display_name, value=f'**{first_votes} votes**.')
                embed.add_field(name=first_member.display_name, value=f'**{second_votes} votes**.')

                if first_votes == second_votes:
                    embed.add_field(
                        name='It Was A Tie!', value='The results were a tie, so we randomized the winner!', inline=False
                    )

                embed.add_field(
                    name='Thank You!',
                    value='From all of us working hard to make the FLVS Fury eSports team everything it is, we thank you '
                    'for your service and hope you will continue to support us in the future. See you next season!',
                )
                embed.set_footer(
                    text=f'You have {GRACE_PERIOD} seconds until you get kicked and we move onto the next member.'
                )

            await ctx.send(embed=embed)

            await asyncio.sleep(GRACE_PERIOD)
            # await ctx.guild.kick(member_to_kick, reason='The kickening has spoken!')

            await ctx.send(random.choice(KICKENING_MESSAGES))

            # Remove the kicked member from the list
            all_kickable_members.remove(member_to_kick)
            random.shuffle(all_kickable_members)

            # If the length of all kickable members is 1, we can stop and announce them the winner
            if len(all_kickable_members) == 1:
                await ctx.send(
                    embed=self.bot.Embed(
                        title='The Winner!',
                        description=f'Congratulations {all_kickable_members[0].mention}, you have won the kickening!',
                    ),
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
                break


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(FurySpecificCommands(bot))
