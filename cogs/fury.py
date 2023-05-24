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

import io
import asyncio
import dataclasses
import random
import string
import textwrap
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

import discord
from discord.ext import commands
from typing_extensions import Self, Type

from utils import BaseCog, Context, human_join, human_timestamp
from utils.images import ImageType, async_merge_images

if TYPE_CHECKING:
    from bot import FuryBot

VOTING_TIME: int = 20
GRACE_PERIOD: int = 20

LEAD_CAPTAIN_ROLE_ID: int = 763384816942448640
CAPTAIN_ROLE_ID: int = 765360488816967722
BOTS_ROLE_ID: int = 763455351332798485

COACH_LAMBART_ID: int = 757663899532132418

KICKENING_OPT_OUT_IDS: List[int] = []

ROO_DEVIL_EMOJI: str = '<:rooDevil:1108541372505538620>'


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
    description="All offline and opted out members have been removed from the server. All remaining members "
    'will be casted for the voting process. **The Kickening will start in 2 minutes.**',
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
    "Voters will be given a 20-second window to cast their vote, following which the results will be shown. "
    "The member who holds the highest number of votes will be given a brief 20-second grace period before their "
    "eventual removal from the server.\n\n"
    f"**TLDR (Too Long Didn't Read)**: Vote to kick people, vote to get kicked {ROO_DEVIL_EMOJI}",
    inline=False,
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
        async with self.parent.lock:
            if interaction.user.id == COACH_LAMBART_ID:
                self.voting_list.extend([interaction.user] * 50)  # type: ignore # Weight of 50 votes.
            else:
                self.voting_list.append(interaction.user)  # type: ignore

            # Edit with the new count
            await interaction.edit_original_response(view=self.parent, embed=self.parent.embed)

        await interaction.followup.send('Your vote has been counted!', ephemeral=True)


@dataclasses.dataclass(init=True)
class Results:
    bot: FuryBot
    winner: discord.Member
    loser: discord.Member
    winner_votes: List[discord.Member]
    loser_votes: List[discord.Member]

    @classmethod
    def from_voting_results(
        cls: Type[Self],
        bot: FuryBot,
        first: discord.Member,
        second: discord.Member,
        first_votes: List[discord.Member],
        second_votes: List[discord.Member],
    ) -> Self:
        if first_votes == second_votes:
            # This is a tie, pick a random member as the winner.
            (winner, winner_votes), (loser, loser_votes) = random.sample([(first, first_votes), (second, second_votes)], 2)
            return cls(bot, winner, loser, winner_votes, loser_votes)

        if len(first_votes) > len(second_votes):
            # First member won
            return cls(bot, first, second, first_votes, second_votes)

        # Second member won
        return cls(bot, second, first, second_votes, first_votes)

    @discord.utils.cached_property
    def winner_vote_count(self) -> int:
        return len(self.winner_votes)

    @discord.utils.cached_property
    def loser_vote_count(self) -> int:
        return len(self.loser_votes)

    @property
    def was_tie(self) -> bool:
        return len(self.winner_votes) == len(self.loser_votes)

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=textwrap.shorten(f'Results Of {self.winner.display_name} vs {self.loser.display_name}', 256),
            description=f'**{self.winner.mention}, your time has come!** You will be kicked!',
            author=self.winner,
        )

        embed.add_field(name=self.winner.display_name, value=f'{self.winner_vote_count} votes.')
        embed.add_field(name=self.loser.display_name, value=f'{self.loser_vote_count} votes.')

        if self.was_tie:
            embed.add_field(
                name='It Was A Tie!', value='The results were a tie, so the winner has been randomized.', inline=False
            )

        embed.set_footer(text=f'You have {GRACE_PERIOD} seconds until you get kicked and we move onto the next member.')

        return embed


class KickeningVoting(discord.ui.View):
    def __init__(self, bot: FuryBot, first: discord.Member, second: discord.Member) -> None:
        super().__init__(timeout=VOTING_TIME)
        self.bot = bot

        self.first: discord.Member = first
        self.second: discord.Member = second

        self.first_votes: List[discord.Member] = []
        self.second_votes: List[discord.Member] = []

        self.lock: asyncio.Lock = asyncio.Lock()

        self.voted_members: Set[int] = set()

        self.add_item(KickeningMemberButton(self, self.first, self.first_votes))
        self.add_item(KickeningMemberButton(self, self.second, self.second_votes))

        self.first_v_second_image: Optional[ImageType] = None

    @property
    def embed(self) -> discord.Embed:
        embed = self.bot.Embed(
            title=textwrap.shorten(f'{self.first.display_name} vs {self.second.display_name}', 256),
            description='Use one of the two buttons below to vote for who you want to see kicked. '
            'You can only vote once per set, so make it count! The person with the most amount of votes will be kicked from the server.',
        )

        embed.add_field(name=self.first.display_name, value=f'**{len(self.first_votes)} votes**.')
        embed.add_field(name=self.second.display_name, value=f'**{len(self.second_votes)} votes**.')

        embed.set_image(url='attachment://kickening.png')

        return embed

    async def interaction_check(self, interaction: discord.Interaction[FuryBot], /) -> Optional[bool]:
        await interaction.response.defer()

        async with self.lock:
            if interaction.user in {self.first, self.second}:
                return await interaction.followup.send('You cannot vote when you\'re up for the kickening!', ephemeral=True)

            if interaction.user in [*self.first_votes, *self.second_votes]:
                return await interaction.followup.send('You cannot vote twice!', ephemeral=True)

        return True

    def get_results(self) -> Results:
        return Results.from_voting_results(self.bot, self.first, self.second, self.first_votes, self.second_votes)

    async def _get_first_v_second_image(self) -> ImageType:
        if self.first_v_second_image is not None:
            return self.first_v_second_image

        async with self.bot.session.get(self.first.display_avatar.url) as response:
            first_bytes = await response.read()

        async with self.bot.session.get(self.second.display_avatar.url) as response:
            second_bytes = await response.read()

        self.first_v_second_image = image = await async_merge_images(
            self.bot, [first_bytes, second_bytes], images_per_row=2, half_size=False, frame_width=1000
        )
        return image

    async def get_first_v_second_file(self) -> discord.File:
        image = await self._get_first_v_second_image()
        buf = io.BytesIO()

        image.save(buf, format='PNG')
        buf.seek(0)

        return discord.File(buf, filename='kickening.png')


class FurySpecificCommands(BaseCog):
    def __init__(self, bot: FuryBot) -> None:
        super().__init__(bot)

        self._kickening_task: Optional[asyncio.Task[None]] = None

    async def _listen_for_members(
        self, ctx: Context, offline_members: List[discord.Member], members_to_kick: List[discord.Member]
    ) -> None:
        def check(message: discord.Message) -> bool:
            if ctx.channel != message.channel:
                return False

            if message.author in offline_members and message.author.id not in KICKENING_OPT_OUT_IDS:
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

                if member.id in KICKENING_OPT_OUT_IDS:
                    offline_members.append(member)
                    continue

                if member.status is discord.Status.offline:
                    offline_members.append(member)
                    continue

                all_kickable_members.append(member)

        random.shuffle(all_kickable_members)

        embed = self.bot.Embed(
            title='Kicking Offline and Opt-Out Members First!',
            description=f'A total of **{len(all_kickable_members) + len(offline_members)} members** have been fetched for the kickening! '
            f'**{len(offline_members)}** of these members are offline or have chosen to opt-out, and as a result, they will be kicked first!',
        )
        embed.add_field(
            name='Offline And Opt-Out Member Kicking',
            value=f'All offline and opt-out members will randomly be kicked first without voting, then afterward all the online members will be submitted '
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

        # await asyncio.sleep(30)
        #
        # for index, offline_member in enumerate(offline_members):
        #     member_information: List[str] = [
        #         '**Roles**: {}'.format(human_join([role.mention for role in list(reversed(offline_member.roles))[:-1]]))
        #     ]
        #     if offline_member.joined_at is not None:
        #         member_information.append(f'**Joined At**: {human_timestamp(offline_member.joined_at)}')
        #     else:
        #         # Thanks discord
        #         maybe_member = ctx.guild.get_member(offline_member.id)
        #         if maybe_member is not None and maybe_member.joined_at is not None:
        #             member_information.append(f'**Joined At**: {human_timestamp(maybe_member.joined_at)}')
        #
        #     if offline_member.premium_since:
        #         member_information.append(f'**Boosting The Server Since**: {human_timestamp(offline_member.premium_since)}')
        #
        #     embed = self.bot.Embed(
        #         title=f'{offline_member.display_name}\'s Time is Up!',
        #         description=f'{offline_member.mention} is offline on Discord or has chosen to opt-out of the kickening. They have 20 seconds '
        #         'before they are kicked if they are an opted-out member, otherwise it\'s an instant boot!',
        #         author=offline_member,
        #     )
        #     embed.add_field(name='Member Information', value='\n'.join(member_information), inline=False)
        #
        #     embed.add_field(
        #         name='Offline/Opt-Out Members Remaining',
        #         value=f'There are **{len(offline_members) - index - 1} members** remaining to be kicked!',
        #         inline=False,
        #     )
        #
        #     message = await ctx.send(
        #         embed=embed,
        #         content=offline_member.mention,
        #         allowed_mentions=discord.AllowedMentions(users=True),
        #     )
        #
        #     if offline_member not in offline_members:
        #         # This member removed themselves
        #         await message.reply('Did not kick member as they removed themselves from the offline member list!')
        #     else:
        #         if offline_member.id in KICKENING_OPT_OUT_IDS:
        #             await asyncio.sleep(20)  # 20 seconds for opted-out members
        #
        #         # await offline_member.kick(reason='Offline member')
        #
        #         kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=offline_member.mention)
        #         await message.reply(kick_message)
        #
        #     # If it's not the last member, sleep for 20 seconds
        #     if index != len(offline_members) - 1:
        #         await asyncio.sleep(20)
        #
        # # End the searching for offline members
        # task.cancel()
        #
        # await ctx.send(embed=KICKENING_EMBED)
        # await asyncio.sleep(60 * 2)  # 2 minutes

        # We're going to use a while True loop here and abuse some mutable objects
        while len(all_kickable_members) > 1:
            kickable_members = determine_kickable_members(all_kickable_members)

            # Spawn a new view
            view = KickeningVoting(self.bot, kickable_members[0], kickable_members[1])
            file = await view.get_first_v_second_file()

            message = await ctx.channel.send(
                embed=view.embed,
                view=view,
                content=human_join((m.mention for m in kickable_members)),
                allowed_mentions=discord.AllowedMentions(users=True),
                file=file,
            )

            await view.wait()

            async with ctx.typing():
                # Now we can get the results of the vote
                results = view.get_results()

                await message.edit(view=None)

                embed = results.embed
                embed.add_field(
                    name='Remaining Members',
                    value=f'There are **{len(all_kickable_members)} people** remaining in the kickening. There is '
                    f'20 seconds before kicking {results.winner.mention} and moving on to the next round!',
                    inline=False,
                )
                embed.set_image(url=message.attachments[0].url)

            message = await message.reply(embed=embed, file=file)

            await asyncio.sleep(GRACE_PERIOD)

            # await ctx.guild.kick(member_to_kick, reason='The kickening has spoken!')

            kick_message = string.Template(random.choice(KICKENING_MESSAGES)).substitute(mention=results.winner.mention)
            await message.reply(kick_message)

            await asyncio.sleep(10)

            # Remove the kicked member from the list
            all_kickable_members.remove(results.winner)
            random.shuffle(all_kickable_members)

        # The length of all kickable members is 1, we can stop and announce them the winner
        await ctx.send(
            embed=self.bot.Embed(
                title='The Winner!',
                description=f'Congratulations {all_kickable_members[0].mention}, you have won the kickening!',
            ),
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    @commands.group(name='kickening', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def kickening(self, ctx: Context) -> None:
        """Commands for the kickening."""
        if ctx.invoked_subcommand is not None:
            return

        await ctx.send('Invalid subcommand passed. Valid subcommands are `start`, `stop`.')

    def _kickening_task_done(self, task: asyncio.Task[None]) -> None:
        exception = task.exception()
        if exception is None:
            return

        if isinstance(exception, asyncio.InvalidStateError):
            # This task is not Done?
            return

        if self.bot.error_handler:
            asyncio.create_task(
                self.bot.error_handler.log_error(exception, origin=None, sender=None, event_name=task.get_name())
            )
        else:
            raise exception

    @kickening.command(name='start', hidden=True)
    @commands.is_owner()
    @commands.guild_only()
    async def start_kickening(self, ctx: Context) -> None:
        """Starts the kickening."""
        self._kickening_task = task = self.bot.create_task(self._wrap_kickening(ctx))
        task.add_done_callback(self._kickening_task_done)

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
