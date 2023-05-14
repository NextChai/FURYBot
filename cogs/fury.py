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
import io
import textwrap
import random
from typing import TYPE_CHECKING, List, Optional, Set, Type
from typing_extensions import Self
from PIL import ImageOps, Image, ImageDraw

import discord
from discord.ext import commands

from utils import BaseCog, Context, human_join
from utils.images import ImageType, sync_merge_images

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
    def __init__(self, parent: KickeningView, member: discord.Member, voting_list: List[discord.Member]) -> None:
        super().__init__(label=textwrap.shorten(f'{member.display_name}', width=80), style=discord.ButtonStyle.red)
        self.parent: KickeningView = parent
        self.member: discord.Member = member
        self.voting_list: List[discord.Member] = voting_list

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        await interaction.response.defer()  # The client's latency will skyrocket, this is precautionary

        async with self.parent.lock:
            self.parent.voting_counter[self.member] += 1
            self.voting_list.append(self.member)

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

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        if interaction.user in {self.first, self.second}:
            return await interaction.response.send_message(
                'You cannot vote when you\'re up for the kickening!', ephemeral=True
            )

        if interaction.user in [*self.first_votes, *self.second_votes]:
            return await interaction.response.send_message('You have already voted!', ephemeral=True)

        return True

    @classmethod
    def crop_to_circle(cls: Type[Self], image: ImageType) -> ImageType:
        # Crop the image to a square
        img = ImageOps.fit(image, (image.size[0], image.size[0]))

        # Create a mask in the shape of a circle
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, img.size[0], img.size[1]), fill=255)

        # Apply the mask to the image
        cropped = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
        cropped.putalpha(mask)

        return cropped

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
        top_image_padding = 10
        bottom_image_padding = 10
        sub_image_bottom_padding = 10
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
                image_alteration=self.crop_to_circle,
            )

        second_member_voters_image: Optional[ImageType] = None
        if second_voters_bytes:
            second_member_voters_image = sync_merge_images(
                second_voters_bytes,
                images_per_row=10,
                frame_width=sub_image_width,
                background_color=(49, 51, 56),
                image_alteration=self.crop_to_circle,
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
        first_member_image = self.crop_to_circle(
            Image.open(io.BytesIO(first_bytes)).resize((main_member_image_height, main_member_image_width))
        )
        image.paste(first_member_image, (middle_of_image - (main_member_image_width // 2), top_image_padding))

        if first_member_voters_image:
            image.paste(first_member_voters_image, (10, 120))

        # Then paste the second members image
        second_member_image = self.crop_to_circle(
            Image.open(io.BytesIO(second_bytes)).resize((main_member_image_height, main_member_image_width))
        )
        image.paste(
            second_member_image, (middle_of_image + (quarter_of_image - (main_member_image_width // 2)), top_image_padding)
        )

        if second_member_voters_image:
            image.paste(second_member_voters_image, (260, 120))

        return image

    async def generate_image(self) -> ImageType:
        # Download first member avatar
        async def _download_image(url: str) -> bytes:
            async with self.bot.session.get(url) as response:
                return await response.read()

        first_member = await _download_image(self.first.display_avatar.url)
        second_member = await _download_image(self.second.display_avatar.url)

        first_voters = await asyncio.gather(*[_download_image(m.display_avatar.url) for m in self.first_votes])
        second_voters = await asyncio.gather(*[_download_image(m.display_avatar.url) for m in self.second_votes])

        return await self.bot.wrap(self._sync_generate_image, first_member, first_voters, second_member, second_voters)


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

        # We're going to use a while True loop here and abuse some mutable objects
        while True:
            # Spawn a new view
            kickable_members = random.choices(all_kickable_members, k=2)

            view = KickeningView(self.bot, kickable_members[0], kickable_members[1])
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
