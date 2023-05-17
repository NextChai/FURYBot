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

import string
import asyncio
import io
import textwrap
import random
from typing import TYPE_CHECKING, List, Optional, Set, Tuple
from PIL import Image

import discord
from discord.ext import commands

from utils import BaseCog, Context, human_join
from utils.images import ImageType, sync_merge_images

if TYPE_CHECKING:
    from bot import FuryBot

VOTING_TIME: int = 20
GRACE_PERIOD: int = 20

LEAD_CAPTAIN_ROLE_ID: int = 763384816942448640
CAPTAIN_ROLE_ID: int = 765360488816967722
BOTS_ROLE_ID: int = 763455351332798485

KICKENING_MESSAGES: List[str] = [
    "Oops! Looks like $mention got kicked! Better luck next time, champ.",
    "Kicked out of the game and the server? Ouch, that's gotta hurt, $mention.",
    "Time to take a break and rethink your strategy, $mention. You've been kicked!",
    "Don't worry, $mention, it's just a kick in the pants. See you soon!",
    "You've been kicked to the curb, $mention. Better dust off your gaming skills.",
    "A kick in the server is worth two in the game, $mention. Time to regroup.",
    "Kicked and banished! Time to work on those team skills, $mention.",
    "Kicked to the sidelines, $mention? Use this time to practice and come back stronger.",
    "Kicked out? That's okay, $mention, there's always room for improvement.",
    "Kicked, but not defeated! Keep pushing for that victory, $mention.",
    "Sorry, but $mention is not living up to the game's standards. Kicked!",
    "Kicked like a ball in Rocket League, $mention. Keep your head up!",
    "No need to rage quit, $mention, you've already been kicked. Come back stronger.",
    "The only way to go is up after getting kicked. Good luck, $mention!",
    "Kicked for being a sore loser? Try being a gracious winner instead, $mention.",
    "Kicked, but still loved. Come back and join the fun again soon, $mention!",
    "A kick in the server is a wake-up call. Time to up your game, $mention!",
    "You can't win them all, but you can learn from getting kicked. Keep going, $mention!",
    "Looks like $mention has been kicked from the game. Time to Overwatch your strategy.",
    "Mario Kart outta here! $mention has been kicked from the server.",
    "Sorry, but $mention is not Smash-ing it today. You've been kicked!",
    "Kicked like a soccer ball in Rocket League? Time to work on your defense, $mention.",
    "We're not Spla-toon with you today. $mention has been kicked from the game.",
    "$mention has been kicked from the server. That's a Valo-rant, don't you think?",
    "League of Legends? More like League of Losers. $mention has been kicked!",
    "Kicked from the server? It's time to Get-Gooder at the game, $mention.",
    "Sorry, $mention, you're not living up to our standards. You've been Overwatch-ed and kicked.",
    "Kicked from the server? Looks like $mention needs to Aimbot-ter next time.",
    "Super Smash Bros? More like Super Smashed by the ban hammer. $mention has been kicked!",
    "Mario Karted out of the server. Time to re-Luigi-n your gaming skills, $mention.",
    "Splatoon? More like Sploosh-gone. $mention has been kicked!",
    "Kicked from the server? That's not very VALOR-ant of us, $mention.",
    "Time to take a break and re-focus, $mention. You've been kicked from the game.",
    "Looks like $mention got the boot! Maybe next time you'll kick it up a notch.",
    "Kicked from the server? Don't worry, $mention, there's always another game to play.",
    "A kick in the pants might be just what you need, $mention. Come back stronger!",
    "Sorry, $mention, but you're out of the game. Time to level up your skills!",
    "Kicked from the game? That's a sign to take a break and come back refreshed, $mention.",
    "Don't be a sore loser, $mention. Accept the kick and learn from it.",
    "Kicked out of the server? That's just a temporary setback, $mention. Keep striving for greatness.",
    "A kick in the server is like a reset button. Use it to your advantage, $mention.",
    "Looks like $mention got the boot! And not the fashionable kind.",
    "Don't worry, $mention. Getting kicked is just the universe's way of telling you to take a break from screens and go outside.",
    "Kicked to the curb like an old can of LaCroix, $mention. Better luck next time.",
    "Kicked from the server? That's okay, $mention, there's always another game to play.",
    "Did someone just kick $mention to the moon? Because they're definitely not on this server anymore.",
    "Looks like $mention just got sent to the penalty box. Better start practicing those power plays.",
    "Sorry, $mention, but we had to give you the boot. We heard you were hoarding all the gold coins.",
    "You can't spell \"kicked\" without \"I C K\" and that's exactly what $mention just got. Ouch.",
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


def determine_kickable_members(all_kickable_members: List[discord.Member]) -> Tuple[discord.Member, discord.Member]:
    while True:
        kickable_members = random.sample(all_kickable_members, 2)
        if kickable_members[0] != kickable_members[1]:
            return kickable_members[0], kickable_members[1]


class KickeningMemberButton(discord.ui.Button['KickeningView']):
    def __init__(self, parent: KickeningView, member: discord.Member, voting_list: List[discord.Member]) -> None:
        super().__init__(label=textwrap.shorten(f'{member.display_name}', width=80), style=discord.ButtonStyle.red)
        self.parent: KickeningView = parent
        self.member: discord.Member = member
        self.voting_list: List[discord.Member] = voting_list

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        await interaction.response.defer()  # The client's latency will skyrocket, this is precautionary

        async with self.parent.lock:
            self.parent.voting_counter[self.member] += 1
            self.voting_list.append(interaction.user)  # type: ignore

            # Edit with the new count
            await interaction.edit_original_response(view=self.parent, embed=self.parent.embed)

        await interaction.followup.send('Your vote has been counted!', ephemeral=True)


class KickeningView(discord.ui.View):
    def __init__(self, bot: FuryBot, first: discord.Member, second: discord.Member) -> None:
        super().__init__(timeout=VOTING_TIME)
        self.bot = bot

        self.first: discord.Member = first
        self.second: discord.Member = second

        self.first_votes: List[discord.Member] = []
        self.second_votes: List[discord.Member] = []

        self.voting_counter: collections.Counter[discord.Member] = collections.Counter()
        self.lock: asyncio.Lock = asyncio.Lock()

        self.voted_members: Set[int] = set()

        self.add_item(KickeningMemberButton(self, self.first, self.first_votes))
        self.add_item(KickeningMemberButton(self, self.second, self.second_votes))

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=textwrap.shorten(f'{self.first.display_name} vs {self.second.display_name}', 256),
            description='Use the two buttons below to choose which member you want to see kicked from the server! Your vot',
        )

        embed.add_field(name=self.first.display_name, value=f'**{self.voting_counter[self.first]} votes**.')
        embed.add_field(name=self.second.display_name, value=f'**{self.voting_counter[self.second]} votes**.')

        embed.set_image(url='attachment://kickening.png')

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        if interaction.user in {self.first, self.second}:
            return await interaction.response.send_message(
                'You cannot vote when you\'re up for the kickening!', ephemeral=True
            )

        if interaction.user in [*self.first_votes, *self.second_votes]:
            return await interaction.response.send_message('You have already voted!', ephemeral=True)

        return True

    def _sync_generate_image(
        self,
        first_bytes: bytes,
        first_voters_bytes: List[bytes],
        second_bytes: bytes,
        second_voters_bytes: List[bytes],
    ) -> ImageType:
        # After some respectable amount of testing, we can determine that a good image size
        # is going to be 500 width.
        image_width = 500

        # There are two bottom images, one for each member. The total image width is 500,
        # and there is a 10px padding between the images and a 10px padding on the left and right.
        sub_image_width = 235

        # Image height needs to be calculated though as it's dynamic.
        # Top border is 10px, image height is 100, bottom border is 10px.
        top_image_padding = 20
        bottom_image_padding = 15
        sub_image_bottom_padding = 20
        main_member_image_height = 100
        main_member_image_width = 100
        image_height = main_member_image_height + top_image_padding + bottom_image_padding + sub_image_bottom_padding

        # Below it is going to be the images showing who voted for who, which
        # is completely dynamic.

        first_member_voters_image: Optional[ImageType] = None
        if first_voters_bytes:
            first_member_voters_image = sync_merge_images(
                first_voters_bytes,
                images_per_row=10,
                frame_width=sub_image_width,
                background_color=(49, 51, 56),
            )

        second_member_voters_image: Optional[ImageType] = None
        if second_voters_bytes:
            second_member_voters_image = sync_merge_images(
                second_voters_bytes,
                images_per_row=10,
                frame_width=sub_image_width,
                background_color=(49, 51, 56),
            )

        # Update the image height to include highest voter image height
        first_height = first_member_voters_image and first_member_voters_image.height or 0
        second_height = second_member_voters_image and second_member_voters_image.height or 0
        image_height += max(first_height, second_height)

        # Now we can create our image
        image = Image.new('RGBA', (image_width, image_height), (49, 51, 56))

        middle_of_image = image_width // 2
        quarter_of_image = image_width // 4

        # First paste the first members image
        first_member_image = Image.open(io.BytesIO(first_bytes)).resize((main_member_image_height, main_member_image_width))
        image.paste(first_member_image, (quarter_of_image - (main_member_image_width // 2), top_image_padding))

        if first_member_voters_image:
            image.paste(
                first_member_voters_image, (10, top_image_padding + main_member_image_height + sub_image_bottom_padding)
            )

        # Then paste the second members image
        second_member_image = Image.open(io.BytesIO(second_bytes)).resize(
            (main_member_image_height, main_member_image_width)
        )
        image.paste(
            second_member_image, (middle_of_image + (quarter_of_image - (main_member_image_width // 2)), top_image_padding)
        )

        if second_member_voters_image:
            image.paste(
                second_member_voters_image, (260, top_image_padding + main_member_image_height + sub_image_bottom_padding)
            )

        return image

    async def generate_image(self) -> discord.File:
        # Download first member avatar
        async def _download_image(url: str) -> bytes:
            async with self.bot.session.get(url) as response:
                return await response.read()

        first_member = await _download_image(self.first.display_avatar.url)
        second_member = await _download_image(self.second.display_avatar.url)

        first_voters = await asyncio.gather(*[_download_image(m.display_avatar.url) for m in self.first_votes])
        second_voters = await asyncio.gather(*[_download_image(m.display_avatar.url) for m in self.second_votes])

        image = await self.bot.wrap(self._sync_generate_image, first_member, first_voters, second_member, second_voters)

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)

        return discord.File(buffer, filename='kickening.png')


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
            members = await self.bot._connection.query_members(
                guild=ctx.guild, query='', limit=0, user_ids=None, cache=False, presences=True
            )
            for member in members:
                if not should_kick_member(member):
                    continue

                if member.status is discord.Status.offline:
                    offline_members.append(member)
                    continue

                all_kickable_members.append(member)

        random.shuffle(all_kickable_members)

        embed = self.bot.Embed(
            title='Fetched All Members',
            description=f'Fetched {len(all_kickable_members) + len(offline_members)} members for the kickening, let it begin in 30 seconds!',
        )
        embed.add_field(
            name='Offline Members!',
            value=f'There are {len(offline_members)} offline members, they will be kicked immediately! You had your chance!',
        )

        await ctx.send(
            embed=embed,
            delete_after=30,
        )

        await asyncio.sleep(30)

        for index, offline_member in enumerate(offline_members):
            kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=offline_member.mention)

            embed = self.bot.Embed(
                title=f'{offline_member.display_name} is offline!',
                description=f'{offline_member.mention} is offline on Discord, so they will not be included in the kickening. Someone '
                f'didn\'t look at <#757666199214751794>!\n\n{kick_message}',
                author=offline_member,
            )
            embed.add_field(
                name='Offline Members Remaining',
                value=f'There are **{len(offline_members) - index - 1} offline members** remaining!',
                inline=False,
            )

            await ctx.send(
                embed=self.bot.Embed(
                    title=f'{offline_member.display_name} is offline!',
                    description=f'{offline_member.mention} is offline on Discord, so they will not be included in the kickening. Someone '
                    f'didn\'t look at <#757666199214751794>!\n\n{kick_message}',
                    author=offline_member,
                ),
                delete_after=20,
                content=offline_member.mention,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            # await offline_member.kick(reason='Offline member')

            await asyncio.sleep(10)

        # We're going to use a while True loop here and abuse some mutable objects
        while True:
            kickable_members = determine_kickable_members(all_kickable_members)

            # Spawn a new view
            view = KickeningView(self.bot, kickable_members[0], kickable_members[1])
            image = await view.generate_image()

            message = await ctx.channel.send(
                embed=view.embed,
                view=view,
                content=human_join((m.mention for m in kickable_members)),
                allowed_mentions=discord.AllowedMentions(users=True),
                files=[image],
            )

            await view.wait()

            async with ctx.typing():
                await message.edit(view=None)

                # Now we can get the results of the vote
                voting_results = view.voting_counter.most_common()

                # If a member doesn't get a vote then they won't be in the results.
                # If there is a tie, we'll randomize the winner
                if len(voting_results) == 1:
                    # Only one member got votes, kick the one that didn't get any
                    first_member, first_votes = voting_results[0]
                    second_member, second_votes = (
                        kickable_members[1] if first_member == kickable_members[0] else kickable_members[0],
                        0,
                    )

                    member_to_kick = second_member
                elif len(voting_results) == 0:
                    # No one voted, shuffle then kicka random member
                    first_member, first_votes = kickable_members[0], 0
                    second_member, second_votes = kickable_members[1], 0

                    member_to_kick = random.choice((first_member, second_member))
                else:
                    first_member, first_votes = voting_results[0]
                    second_member, second_votes = voting_results[1]

                    if first_votes == second_votes:
                        # This is a tie, randomize the winner
                        member_to_kick = random.choice(voting_results)[0]
                    else:
                        member_to_kick = first_member if first_votes < second_votes else second_member

                embed = self.bot.Embed(
                    title=textwrap.shorten(f'Results Of {first_member.display_name} vs {second_member.display_name}', 256),
                    description=f'I\'m sorry {member_to_kick.mention}, but your time has come! You will be kicked!',
                    author=member_to_kick,
                )

                embed.add_field(name=first_member.display_name, value=f'{first_votes} votes.')
                embed.add_field(name=second_member.display_name, value=f'{second_votes} votes.')

                if first_votes == second_votes:
                    embed.add_field(
                        name='It Was A Tie!', value='The results were a tie, so we randomized the winner!', inline=False
                    )

                embed.add_field(
                    name='Thank You!',
                    value='From all of us working hard to make the FLVS Fury eSports team everything it is, we thank you '
                    'for your service and hope you will continue to support us in the future. See you next season!',
                    inline=False,
                )
                embed.add_field(
                    name='Remaining Members',
                    value=f'There are **{len(all_kickable_members)} people** remaining in the kickening.',
                    inline=False,
                )

                embed.set_footer(
                    text=f'You have {GRACE_PERIOD} seconds until you get kicked and we move onto the next member.'
                )

                file = await view.generate_image()
                embed.set_image(url=f'attachment://{file.filename}')

            message = await message.reply(embed=embed, files=[file])

            await asyncio.sleep(GRACE_PERIOD)

            # await ctx.guild.kick(member_to_kick, reason='The kickening has spoken!')

            kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=member_to_kick.mention)
            await message.reply(kick_message)

            await asyncio.sleep(10)

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
