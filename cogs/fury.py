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

import cachetools
import dataclasses
import string
import asyncio
import io
import textwrap
import random
from typing import TYPE_CHECKING, List, Optional, Set, Tuple
from typing_extensions import Self, Type

import PIL
from PIL import Image, ImageFont, ImageDraw

import discord
from discord.ext import commands

from utils import BaseCog, Context, human_join, human_timestamp
from utils.images import ImageType, sync_merge_images

if TYPE_CHECKING:
    from bot import FuryBot

PIL_CORE = PIL._imagingft  # type: ignore

VOTING_TIME: int = 20
GRACE_PERIOD: int = 20

LEAD_CAPTAIN_ROLE_ID: int = 763384816942448640
CAPTAIN_ROLE_ID: int = 765360488816967722
BOTS_ROLE_ID: int = 763455351332798485

ROO_DEVIL_EMOJI: str = '<:rooDevil:1108541372505538620>'

SCORE_FONT_SIZE: int = 57

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

KICKENING_EMBED = discord.Embed(
    title="The Kickening Is Near!",
    description="Below describes the details of The Kickening! Be sure to read everything so you know how it works!",
)
KICKENING_EMBED.add_field(
    name="What Is The Kickening?",
    value="During the summer, all students must be removed from our Discord server. "
    "These students are not enrolled in any FLVS classes, therefore are not eligible for any FLVS clubs. "
    "Additionally, the server undergoes renovations and trains Captains during this time. The past couple of seasons <@146348630926819328> has "
    "made a game out of this event, and the community coined it as The Kickening:tm:.",
    inline=False,
)
KICKENING_EMBED.add_field(
    name="So How Does The Kickening Work?",
    value="This year's Kickening is a randomized voting event! Two members will be selected at random, "
    f"after which all other participants will have the opportunity to vote for the person they want to see kicked {ROO_DEVIL_EMOJI}! "
    "Each voter will be given a 20-second window to cast their vote, following which the results will be shown. "
    "The member who holds the highest number of votes will be given a brief 20-second grace period before their "
    "eventual removal from the server. An example image of voting results has been attached below.\n\n"
    f"**TLDR (Too Long Didn't Read)**: Vote to kick people, see who betrays you {ROO_DEVIL_EMOJI}",
    inline=False,
)
KICKENING_EMBED.set_image(
    url='https://media.discordapp.net/attachments/887771983792701480/1108564025857560618/kickening.png?width=449&height=566'
)


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


class KickeningMemberButton(discord.ui.Button['KickeningVoting']):
    def __init__(self, parent: KickeningVoting, member: discord.Member, voting_list: List[discord.Member]) -> None:
        super().__init__(label=textwrap.shorten(f'{member.display_name}', width=80), style=discord.ButtonStyle.red)
        self.parent: KickeningVoting = parent
        self.member: discord.Member = member
        self.voting_list: List[discord.Member] = voting_list

    async def callback(self, interaction: discord.Interaction[FuryBot]) -> None:
        await interaction.response.defer()  # The client's latency will skyrocket, this is precautionary

        async with self.parent.lock:
            self.voting_list.append(interaction.user)  # type: ignore

            # Edit with the new count
            await interaction.edit_original_response(view=self.parent, embed=self.parent.embed)

        await interaction.followup.send('Your vote has been counted!', ephemeral=True)


@dataclasses.dataclass(init=True)
class Results:
    cog: FurySpecificCommands
    winner: discord.Member
    loser: discord.Member
    winner_votes: List[discord.Member]
    loser_votes: List[discord.Member]

    @classmethod
    def from_voting_results(
        cls: Type[Self],
        cog: FurySpecificCommands,
        first: discord.Member,
        second: discord.Member,
        first_votes: List[discord.Member],
        second_votes: List[discord.Member],
    ) -> Self:
        if first_votes == second_votes:
            # This is a tie, pick a random member as the winner.
            (winner, winner_votes), (loser, loser_votes) = random.sample([(first, first_votes), (second, second_votes)], 2)
            return cls(cog, winner, loser, winner_votes, loser_votes)

        if first_votes > second_votes:
            # First member won
            return cls(cog, first, second, first_votes, second_votes)

        # Second member won
        return cls(cog, second, first, second_votes, first_votes)

    @classmethod
    async def fetch_partial_image(
        cls: Type[Self], cog: FurySpecificCommands, first: discord.Member, second: discord.Member
    ) -> discord.File:
        temp = cls(cog, first, second, [], [])
        return await temp.generate_image()

    @discord.utils.cached_property
    def winner_vote_count(self) -> int:
        return len(self.winner_votes)

    @discord.utils.cached_property
    def loser_vote_count(self) -> int:
        return len(self.loser_votes)

    @property
    def was_tie(self) -> bool:
        return self.winner_votes == self.loser_votes

    @property
    def bot(self) -> FuryBot:
        return self.cog.bot

    def _sync_generate_image(
        self,
        winner_bytes: bytes,
        winner_voters_bytes: List[bytes],
        loser_bytes: bytes,
        loser_voters_bytes: List[bytes],
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

        font_padding_top = 20

        image_height = (
            main_member_image_height + top_image_padding + bottom_image_padding + sub_image_bottom_padding + font_padding_top
        )

        # Below it is going to be the images showing who voted for who, which
        # is completely dynamic.

        winner_member_voters_image: Optional[ImageType] = None
        if winner_voters_bytes:
            winner_member_voters_image = sync_merge_images(
                winner_voters_bytes,
                images_per_row=5,
                frame_width=sub_image_width,
                background_color=(49, 51, 56),
            )

        loser_member_voters_image: Optional[ImageType] = None
        if loser_voters_bytes:
            loser_member_voters_image = sync_merge_images(
                loser_voters_bytes,
                images_per_row=5,
                frame_width=sub_image_width,
                background_color=(49, 51, 56),
            )

        # Update the image height to include highest voter image height
        winner_height = winner_member_voters_image and winner_member_voters_image.height or 0
        loser_height = loser_member_voters_image and loser_member_voters_image.height or 0
        image_height += max(winner_height, loser_height)

        # We need to paste the given scores onto the image.
        winner_voter_count = f'{len(winner_voters_bytes)} Votes'
        loser_voter_count = f'{len(loser_voters_bytes)} Votes'

        # We'll use the longer of the two strings to determine the font size.
        chosen_count = winner_voter_count if len(winner_voter_count) > len(loser_voter_count) else loser_voter_count

        font_size = 74
        font = ImageFont.truetype('./assets/fonts/burbank.otf', font_size)
        while font.getsize(chosen_count)[0] > sub_image_width:
            font_size -= 1
            winner_font.font = PIL_CORE.getfont(  # type: ignore
                './assets/fonts/burbank.otf',
                font_size,
                font.index,
                font.encoding,
                layout_engine=font.layout_engine,
            )

        max_font_height = font.getsize(chosen_count)[1]
        total_font_height = max_font_height + font_padding_top

        image_height += total_font_height

        # Now we can create our image
        image = Image.new('RGBA', (image_width, image_height), (49, 51, 56))
        draw = ImageDraw.Draw(image)

        middle_of_image = image_width // 2
        quarter_of_image = image_width // 4

        # First paste the first members image
        winner_member_image = Image.open(io.BytesIO(winner_bytes)).resize(
            (main_member_image_height, main_member_image_width)
        )
        image.paste(winner_member_image, (quarter_of_image - (main_member_image_width // 2), top_image_padding))

        # Paste the winner voter count, it's x-coordinate is going to be the same as the
        if winner_member_voters_image:
            image.paste(
                winner_member_voters_image,
                (10, top_image_padding + main_member_image_height + sub_image_bottom_padding + total_font_height),
            )

        # Paste the voting number
        winner_count_width, _winner_count_height = font.getsize(winner_voter_count)

        blank_space_per_side = (sub_image_width - winner_count_width) // 2

        draw.text(  # type: ignore
            (10 + blank_space_per_side, top_image_padding + main_member_image_height + font_padding_top),
            winner_voter_count,
            font=font,
            fill=(92, 235, 136),
        )

        # Then paste the second members image
        second_member_image = Image.open(io.BytesIO(loser_bytes)).resize((main_member_image_height, main_member_image_width))
        image.paste(
            second_member_image, (middle_of_image + (quarter_of_image - (main_member_image_width // 2)), top_image_padding)
        )

        if loser_member_voters_image:
            image.paste(
                loser_member_voters_image,
                (260, top_image_padding + main_member_image_height + sub_image_bottom_padding + total_font_height),
            )

        # Paste the second voting number
        loser_count_width, _loser_count_height = font.getsize(loser_voter_count)

        blank_space_per_side = (sub_image_width - loser_count_width) // 2

        draw.text(  # type: ignore
            (260 + blank_space_per_side, top_image_padding + main_member_image_height + font_padding_top),
            loser_voter_count,
            font=font,
            fill=(237, 66, 69),
        )

        return image

    async def generate_image(self) -> discord.File:
        # Download first member avatar
        async def _download_image(member_id: int, url: str) -> bytes:
            maybe_downloaded = self.cog.avatar_cache.get(member_id)
            if maybe_downloaded is not None:
                return maybe_downloaded

            async with self.bot.session.get(url) as response:
                data = await response.read()

            self.cog.avatar_cache[member_id] = data
            return data

        winner = await _download_image(self.winner.id, self.winner.display_avatar.url)
        loser = await _download_image(self.loser.id, self.loser.display_avatar.url)

        winner_votes = await asyncio.gather(*[_download_image(m.id, m.display_avatar.url) for m in self.winner_votes])
        loser_votes = await asyncio.gather(*[_download_image(m.id, m.display_avatar.url) for m in self.loser_votes])

        image = await self.bot.wrap(self._sync_generate_image, winner, winner_votes, loser, loser_votes)

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)

        return discord.File(buffer, filename='kickening.png')


class KickeningVoting(discord.ui.View):
    def __init__(self, cog: FurySpecificCommands, first: discord.Member, second: discord.Member) -> None:
        super().__init__(timeout=VOTING_TIME)
        self.cog: FurySpecificCommands = cog
        self.bot = cog.bot

        self.first: discord.Member = first
        self.second: discord.Member = second

        self.first_votes: List[discord.Member] = []
        self.second_votes: List[discord.Member] = []

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

        embed.add_field(name=self.first.display_name, value=f'**{len(self.first_votes)} votes**.')
        embed.add_field(name=self.second.display_name, value=f'**{len(self.second_votes)} votes**.')

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

    def get_results(self) -> Results:
        return Results.from_voting_results(self.cog, self.first, self.second, self.first_votes, self.second_votes)


class FurySpecificCommands(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

        self._kickening_task: Optional[asyncio.Task[None]] = None
        self.avatar_cache: cachetools.LFUCache[int, bytes] = cachetools.LFUCache(maxsize=100)

    async def _listen_for_members(
        self, ctx: Context, offline_members: List[discord.Member], members_to_kick: List[discord.Member]
    ) -> None:
        def check(message: discord.Message) -> bool:
            if ctx.channel != message.channel:
                return False

            if message.author in offline_members:
                return True

            return False

        while True:
            message = await self.bot.wait_for('message', check=check, timeout=None)
            if isinstance(message.author, discord.Member):
                offline_members.remove(message.author)
                members_to_kick.append(message.author)

                await message.reply(
                    f'Welcome online {message.author.mention}! You have been removed from the offline members list and added to the kickening list! In the mean time, '
                    'view <#757666199214751794> to see the announcements you missed.',
                    allowed_mentions=discord.AllowedMentions(users=True),
                )

    async def _wrap_kickening(self, ctx: Context) -> None:
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
            title='Kicking Offline Members First!',
            description=f'A total of **{len(all_kickable_members) + len(offline_members)} members** have been fetched for the kickening! '
            f'**{len(offline_members)}** of these members are offline, and as a result, they will be kicked first!',
        )
        embed.add_field(
            name='Offline Member Kicking',
            value=f'All offline members will randomly be kicked first without voting, then afterward all the online members will be submitted '
            'for voting! If you come online during this time and type in this channel, you will be removed from the offline member list '
            'and be submitted for voting!',
        )

        await ctx.send(
            embed=embed,
            delete_after=30,
        )

        task = self.bot.loop.create_task(
            self._listen_for_members(ctx, offline_members, all_kickable_members), name='kickening-offline-member-searching'
        )

        await asyncio.sleep(30)

        for index, offline_member in enumerate(offline_members):
            kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=offline_member.mention)

            member_information: List[str] = [
                '**Roles**: {}'.format(human_join([role.mention for role in list(reversed(offline_member.roles))[:-1]]))
            ]
            if offline_member.joined_at is not None:
                member_information.append(f'**Joined At**: {human_timestamp(offline_member.joined_at)}')
            else:
                # Thanks discord
                maybe_member = ctx.guild.get_member(offline_member.id)
                if maybe_member is not None and maybe_member.joined_at is not None:
                    member_information.append(f'**Joined At**: {human_timestamp(maybe_member.joined_at)}')

            if offline_member.premium_since:
                member_information.append(f'**Boosting The Server Since**: {human_timestamp(offline_member.premium_since)}')

            embed = self.bot.Embed(
                title=f'{offline_member.display_name} is offline!',
                description=f'{offline_member.mention} is offline on Discord, so they will not be included in the kickening. Someone '
                f'didn\'t look at <#757666199214751794>!\n\n{kick_message}',
                author=offline_member,
            )
            embed.add_field(name='Member Information', value='\n'.join(member_information), inline=False)

            embed.add_field(
                name='Offline Members Remaining',
                value=f'There are **{len(offline_members) - index - 1} offline members** remaining to be kicked!',
                inline=False,
            )

            await ctx.send(
                embed=embed,
                delete_after=25,
                content=offline_member.mention,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

            # await offline_member.kick(reason='Offline member')

            # If it's not the last member, sleep for 20 seconds
            if index != len(offline_members) - 1:
                await asyncio.sleep(20)

        await ctx.send(embed=KICKENING_EMBED)
        await asyncio.sleep(60 * 2)  # 2 minutes

        # We're going to use a while True loop here and abuse some mutable objects
        while True:
            kickable_members = determine_kickable_members(all_kickable_members)

            # Spawn a new view
            view = KickeningVoting(self, kickable_members[0], kickable_members[1])

            partial_image = await Results.fetch_partial_image(self, kickable_members[0], kickable_members[1])

            message = await ctx.channel.send(
                embed=view.embed,
                view=view,
                content=human_join((m.mention for m in kickable_members)),
                allowed_mentions=discord.AllowedMentions(users=True),
                files=[partial_image],
            )

            await view.wait()

            async with ctx.typing():
                await message.edit(view=None)

                # Now we can get the results of the vote
                results = view.get_results()

                embed = self.bot.Embed(
                    title=textwrap.shorten(f'Results Of {results.winner.display_name} vs {results.loser.display_name}', 256),
                    description=f'**{results.winner.mention}, your time has come!** You will be kicked!',
                    author=results.winner,
                )

                embed.add_field(name=results.winner.display_name, value=f'{results.winner_vote_count} votes.')
                embed.add_field(name=results.loser.display_name, value=f'{results.loser_vote_count} votes.')

                if results.was_tie:
                    embed.add_field(
                        name='It Was A Tie!', value='The results were a tie, so I randomized the winner!', inline=False
                    )

                embed.add_field(
                    name='Remaining Members',
                    value=f'There are **{len(all_kickable_members)} people** remaining in the kickening.',
                    inline=False,
                )

                embed.set_footer(
                    text=f'You have {GRACE_PERIOD} seconds until you get kicked and we move onto the next member.'
                )

                file = await results.generate_image()
                embed.set_image(url=f'attachment://{file.filename}')

            message = await message.reply(embed=embed, files=[file])

            await asyncio.sleep(GRACE_PERIOD)

            # await ctx.guild.kick(member_to_kick, reason='The kickening has spoken!')

            kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=results.winner.mention)
            await message.reply(kick_message)

            await asyncio.sleep(10)

            # Remove the kicked member from the list
            all_kickable_members.remove(results.winner)
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

        # End the searching for offline members
        task.cancel()

    @commands.group(name='kickening', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def kickening(self, ctx: Context) -> None:
        """Commands for the kickening."""
        await ctx.send('Invalid subcommand passed. Valid subcommands are `start`, `stop`.')

    @kickening.command(name='start', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def start_kickening(self, ctx: Context) -> None:
        """Starts the kickening."""
        self._kickening_task = self.bot.create_task(self._wrap_kickening(ctx))

    @kickening.command(name='stop', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def stop_kickening(self, ctx: Context) -> None:
        """Stops the kickening."""
        if self._kickening_task is None:
            await ctx.send('The kickening is not currently running!')
            return

        self._kickening_task.cancel()

        try:
            await self._kickening_task
        except asyncio.CancelledError:
            # This is good, we want this
            pass

        self._kickening_task = None

        await ctx.send('The kickening has been stopped.')


async def setup(bot: FuryBot) -> None:
    await bot.add_cog(FurySpecificCommands(bot))
