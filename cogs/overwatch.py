import json
from typing import (
    Optional,
    Dict,
    TYPE_CHECKING
)

import asyncio
import aiofile
import aiofiles

import discord
from discord.errors import Forbidden, HTTPException
from discord.ext import commands

from cogs.utils.constants import BATTLENET, XBOX, PSN
from cogs.utils.context import Context

if TYPE_CHECKING:
    from bot import FuryBot


def setup(bot):
    bot.add_cog(OWCog(bot))


class PlatformView(discord.ui.View):
    __slots__ = ('platform',)

    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.platform = None

    @discord.ui.button(emoji=BATTLENET)
    async def battlenet(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.platform = 'battlenet'
        self.stop()

    @discord.ui.button(emoji=XBOX)
    async def xbox(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.platform = 'xbl'
        self.stop()

    @discord.ui.button(emoji=PSN)
    async def psn(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.platform = 'psn'
        self.stop()


def _convert_platform(platform) -> str:
    return 'pc' if platform == 'battlenet' else platform


class OWCog(commands.Cog, name='Overwatch'):
    """Overwatch based commands"""

    __slots__ = ('bot', 'ow_json')

    def __init__(self, bot) -> None:
        self.bot: 'FuryBot' = bot
        self.ow_json: str = self.bot.DEFAULT_BASE_PATH + '/json/ow.json'

    async def get_ow_user(self, user_id: Optional[int] = None, *, get_all: bool = False) -> Optional[Dict[str, str]]:
        async with aiofile.async_open(self.ow_json, 'r') as f:
            data = json.loads(await f.read())

        if get_all:
            return data
        return data.get(str(user_id))

    async def save_ow_user(self, key, value) -> int:
        data = await self.get_ow_user(get_all=True)
        data[key] = value

        return await(await aiofiles.open(self.ow_json, mode='w+')).write(json.dumps(data, indent=4))

    async def get_data_from(self, user) -> dict:
        base = 'https://owapi.io/stats/{platform}/us/{battletag}'.format(
            platform=_convert_platform(user['platform']),
            battletag=user['platformUserIdentifier'].replace('#', '-')
        )
        async with self.bot.session.get(base) as resp:
            return await resp.json()

    async def verify_user_and_get_data(self, ctx, member: Optional[discord.Member] = None, *, special: bool = False) -> Optional[dict]:
        member = member or ctx.author
        user = await self.get_ow_user(member.id)
        if not user:
            await ctx.reply(f'{member.mention} has not setup their overwatch data.', mention_author=False)
            return None

        data = await self.get_data_from(user)
        if special:
            return data

        if data['private']:
            await ctx.reply(f'{member.mention}s profile is private, I am unable to do this.')
            return None

        return data

    @commands.group(
        brief='Verify the overwatch setup of another member.',
        description='Verify the overwatch setup of another member.',
        aliases=['ow'],
        invoke_without_command=True)
    async def overwatch(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        """
        Verify the overwatch setup of another member.
        
        **Parameters**
        --------------
        member: member: Optional[discord.Member] = None
            The member to mention
        
        **How to use**
        --------------
        `!overwatch Optional[<member>]`
        
        **Use Example**
        ---------------
        `!overwatch @Trevor F.`
        """
        if ctx.invoked_subcommand:
            return

        member = member or ctx.author
        user = await self.get_ow_user(member.id)
        username = user['platformUserIdentifier']

        data = await self.get_data_from(user)

        portrait = data.get('portrait')
        level = data.get('level')
        embed: discord.Embed = self.bot.Embed(
            title=f'Overwatch Info for {username}',
            description=f'**Name**: {username}\n' \
                        f'**Level**: {level}\n'
        )
        embed.set_thumbnail(url=portrait)
        embed.add_field(name='Acct private?', value=data['private'])

        return await ctx.reply(embed=embed, mention_author=False)

    @overwatch.command(
        name='topheroes',
        brief='View the info on your top heroes',
        description='Get the deeds on your top heroes',
        aliases=['top_heroes'])
    async def overwatch_topheroes(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        portrait = data.get('portrait')
        level = data.get('level')
        heroes = data['stats']['top_heroes']
        quickplay = heroes['quickplay']
        comp = heroes['competitive']

        e: discord.Embed = self.bot.Embed(
            title=f'Overwatch Info for {username}',
            description=f'**Name**: {username}\n' \
                        f'**Level**: {level}\n'
        )
        e.set_thumbnail(url=portrait)

        formatted = {}
        for element, list in quickplay.items():
            if not list:
                continue

            item = list[0]
            formatted[element] = {'quickplay': f"{item['hero']} :: {item[element]}", 'comp': ''}

        for element, list in comp.items():
            if not list:
                continue

            item = list[0]
            try:
                formatted[element]['comp'] = f"{item['hero']} :: {item[element]}"
            except KeyError:
                formatted[element] = {}
                formatted[element]['comp'] = f"{item['hero']} :: {item[element]}"
                formatted[element]['quickplay'] = 'N/a'

        for format, item in formatted.items():
            e.add_field(name=format.replace('_', ' ').capitalize(),
                        value='**Quickplay:** {quick}\n**Competitive**: {comp}'.format(
                            quick=item.get('quickplay'),
                            comp=item['comp']
                        ))

        return await ctx.reply(embed=e, mention_author=False)

    async def format_data_from(self, data: dict, type: str) -> discord.Embed:
        username = data.get('username')
        portrait = data.get('portrait')
        level = data.get('level')
        heroes = data['stats'][type]

        e: discord.Embed = self.bot.Embed(
            title=f'Overwatch Info for {username}',
            description=f'**Name**: {username}\n' \
                        f'**Level**: {level}\n\n'
        )
        e.set_thumbnail(url=portrait)

        quickplay = heroes['quickplay']
        comp = heroes['competitive']

        _formatted_quickplay = ''
        _formatted_comp = ''
        for element in quickplay:
            formatted = "{:,}".format(int(element["value"])) if element['value'].isdigit() else element['value']
            _formatted_quickplay += f'**{element["title"]}**: {formatted}\n'

        for element in comp:
            formatted = "{:,}".format(int(element["value"])) if element['value'].isdigit() else element['value']
            _formatted_comp += f'**{element["title"]}**: {formatted}\n'

        e.description += f'**Quickplay**:\n{_formatted_quickplay}\n**Competitive:**\n{_formatted_comp}'
        return e

    @overwatch.command(
        name='combat',
        brief='View the info on the combat records.',
        description='View the info on the combat records.')
    async def overwatch_combat(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'combat')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='matchawards',
        brief='View some info about match awards.',
        description='View some info about match awards',
        aliases=['match_awards'])
    async def overwatch_matchawards(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'match_awards')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='assists',
        brief='View some info on assists.',
        description='View some info on assists.')
    async def overwatch_assists(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'assists')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='average',
        brief='View some averages info.',
        description='View some averages info.',
        aliaes=['averages'])
    async def overwatch_average(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'average')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='miscellaneous',
        brief='View some miscellaneous info.',
        description='View some miscellaneous info.',
        aliaes=['misc'])
    async def overwatch_miscellaneous(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'miscellaneous')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='best',
        brief='View some bests',
        description='View some info on the bests.',
        aliaes=['bests'])
    async def overwatch_best(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'best')
        return await ctx.reply(embed=e, mention_author=False)

    @overwatch.command(
        name='game',
        brief='View some overall game info.',
        description='View overall game info.',
        aliaes=['overall'])
    async def overwatch_game(self, ctx: Context, member: Optional[discord.Member] = None) -> Optional[discord.Message]:
        data = await self.verify_user_and_get_data(ctx, member)
        if not data:
            return

        e = await self.format_data_from(data, 'game')
        return await ctx.reply(embed=e, mention_author=False)

    async def wait_for(self, author):
        try:
            message = await self.bot.wait_for(
                'message',
                check=lambda msg: msg.author == author and not msg.guild,
                timeout=3600
            )
        except asyncio.TimeoutError:
            return None
        else:
            return message

    @overwatch.command(
        name='setup',
        brief='Setup your Overwatch Profile',
        description='Setup your Overwatch Profile')
    @commands.guild_only()
    async def overwatch_setup(self, ctx: Context) -> Optional[discord.Message]:
        channel = await ctx.author.create_dm()

        _orig_embed = self.bot.Embed()
        _orig_embed.title = 'Messaging you now...'
        _orig_embed.description = 'I am trying to DM you now, go through the steps sent in our Private Messages.'
        message = await ctx.reply(embed=_orig_embed, mention_author=False)

        e = self.bot.Embed()
        e.title = 'I need your Overwactch platform!'
        e.description = 'Click the button that corresponds to your platform.'
        view = PlatformView()

        try:
            await channel.send(embed=e, view=view)
        except (HTTPException, Forbidden):
            _orig_embed.title = 'Noo!'
            _orig_embed.description = 'I am unable to DM you! Make sure I can message you then try again!'
            return await message.edit(embed=_orig_embed, content=ctx.author.mention)

        await view.wait()
        platform = view.platform

        e = self.bot.Embed()
        e.title = 'I need your Overwatch name!'
        e.description = "I need your handle on Battle.net (including #)"
        e.add_field(name='What to do?', value='Type me your name and send it to me.')
        await channel.send(embed=e)
        platform_user_identifier = await self.wait_for(ctx.author)
        if not platform_user_identifier:
            _orig_embed.title = 'Timeout'
            _orig_embed.description = f'{ctx.author.mention} has timed out, they did not finish the setup process.'
            await message.edit(embed=_orig_embed)
            return await channel.send('Aborted')

        await self.save_ow_user(str(ctx.author.id),
                                {'platform': platform, 'platformUserIdentifier': platform_user_identifier.content})

        e = self.bot.Embed()
        e.title = 'Done!'
        e.description = 'Thank you!'
        e.add_field(name='What can I do now?', value='Try out **!overwatch** in the <#881935961972436992> channel \:)')
        await channel.send(embed=e)

        _orig_embed.title = 'Success!'
        _orig_embed.description = f'{ctx.author.mention} has finished.\n\n**Platform:** {platform.capitalize()}\n**OW Name:** {platform_user_identifier.content}'
        await ctx.send(embed=_orig_embed)

    @overwatch.command(
        name='change',
        brief='Change your Overwatch Profile',
        description='Change your Overwatch Profile')
    @commands.guild_only()
    async def overwatch_change(self, ctx: Context) -> Optional[discord.Message]:
        data = await self.get_ow_user(get_all=True)
        if data.get(str(ctx.author.id)):
            return await ctx.reply('You are not setup, so you are all set :)', mention_authour=False)

        data.pop(str(ctx.author.id))
        await(await aiofiles.open(self.ow_json, mode='w+')).write(json.dumps(data, indent=4))

        command = self.bot.get_command('overwatch setup')
        return await ctx.invoke(command, *[], **{})
