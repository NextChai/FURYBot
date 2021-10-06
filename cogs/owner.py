import discord
from discord.ext import commands

import textwrap
import io
import traceback
from contextlib import redirect_stdout


def setup(bot):
    bot.add_cog(Owner(bot))

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.slash(
        name='debug',
        description='Toggle the debug feature of the bot.',
        options=[
            commands.CommandOption(
                'enabled',
                'To enable or disable debug',
                type=commands.OptionType.string,
                choices=[
                    commands.CommandOptionChoice(name='Enabled', value='true'),
                    commands.CommandOptionChoice(name='Disabled', value='false')
                ]
            )
        ]
    )
    @commands.is_owner()
    async def debug(self, ctx, enable: str):
        converter = {
            'true': True,
            'false': False
        }
        self.bot.debug = converter[enable]
        
        e = self.bot.Embed(
            title='Success!',
            description='The bots debug has been toggled.'
        )
        return await ctx.send(embed=e)
    
    @commands.slash(
        name='python',
        description='Run code.',
        options=[
            commands.CommandOption('code', 'The code to evaluate', required=True)
        ]
    )
    @commands.is_owner()
    async def python(ctx, code: str):
        globalns = {
            'ctx': ctx,
            'guild': ctx.guild,
            'author': ctx.author,
            'discord': discord,
            'utils': discord.utils,
            'bot': ctx.bot,
        }
        
        globalns.update(globals())
        
        stdout = io.StringIO()
        code = code.replace('```python', '```').replace('```', '')
        to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'
        
        try:
            exec(to_compile, globalns)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')
        
        func = globalns['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                await ctx.send(f'```py\n{value}{ret}\n```')