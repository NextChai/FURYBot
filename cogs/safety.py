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

import discord
from discord.ext import commands, tasks

import re
import aiohttp
import logging
from typing import TYPE_CHECKING

from cogs.utils.checks import should_ignore
from cogs.utils import constants
from cogs.utils.enums import Reasons

if TYPE_CHECKING:
    from bot import FuryBot
    
__all__ = (
    'Safety',
)
    
log = logging.getLogger(__name__)


class Safety(commands.Cog):
    """Used to keep the server "safe". 
    
    Determines if:
    
        - A message has links
        - A message has profanity
        - A member has a bad display name
        - A member has updated their display name to an inappropriate one.
        - A binary message has profanity
        - A message has tried to mention @here or @everyone
        - A message has been uploaded with images or files
        - A message's content legnth is too long.
        - A profanity check on messages that have been edited
        - A member's status is profane.
        
    Attributes
    ----------
    bot: :class:`FuryBot`
        The bot that owns this cog.
    """
    def __init__(self, bot):
        self.bot: FuryBot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession(loop=self.bot.loop)
        
        self.name_checker.start()
        self.load_profanity.start()
        
    @commands.Cog.listener('on_message')
    async def role_mention_checker(self, message: discord.Message) -> None:
        """|coro|
        
        Used to check if a member has successfully mentioned a role. If a member
        was able to mention a role, lockdown the channel and alert those affected.
        """
        if should_ignore(message.author) or message.webhook_id:
            return
        
        if not message.role_mentions:
            return
        
        await message.delete()
        
        await self.bot.lockdown_for(60*10, member=message.author, reason=Reasons.role_mention)
        
        # The user has mentioned a role in their message, let's manage cleanup.
        # Let's limit the channel to only moderators.
        channel = message.channel
        overwrites = channel.overwrites
        overwrites[channel.guild.default_role] = discord.PermissionOverwrite(send_messages=False)
        await channel.edit(overwrites=overwrites)
        
        # Alert those affected
        embed = self.bot.Embed(
            title='Oh No!',
            description='It seems an anauthorized user was able to ping a role in this channel. '
                        'We\'re very sorry for the inconvience, but we\'ve locked this channel down '
                        'in the meant time until we can resolve this issue.',
        )
        embed.set_author(name=message.guild.name, icon_url=message.guild.icon.url if message.guild.icon else None)
        await channel.send(embed=embed)
        
        # DM the author now about the issues
        embed = self.bot.Embed(
            title='Role Mentions Found',
            description=f'{message.author.mention}, it seems you\'ve mentioned a role in your message. This should not '
                        'be possible.'
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name='Role(s) mentioned', value=', '.join(r.mention for r in message.role_mentions))
        await self.send_to(message.author, embed=embed)
        
        # Now let's send it to the logging channel
        embed = self.bot.Embed(
            title='Role Mentions Found',
            description=f'A role mention was found in {channel.mention} sent by {message.author.mention}'
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name='Role(s) mentioned', value=', '.join(r.mention for r in message.role_mentions))
        await self.bot.send_to_logging_channel(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        
    @commands.Cog.listener('on_message')
    async def mention_checker(self, message: discord.Message) -> None:
        """|coro|
        
        Used to check if a user is trying to mention @here or @everyone. If they 
        manage to ping @here or @everyone, lockdown the channel and alert those affected.
        """
        if should_ignore(message.author) or message.webhook_id:
            return
        
        if not message.mention_everyone:
            # The mention_everyone attr does not check if the @everyone 
            # or the @here text is in the message itself. Rather this boolean 
            # indicates if either the @everyone or the @here text is in the message 
            # and it **did** end up mentioning.
            return
        
        await message.delete()

        await self.bot.lockdown_for(60*10, member=message.author, reason=Reasons.mass_mention)
        
        # The user has mentioned a role in their message, let's manage cleanup.
        # Let's limit the channel to only moderators.
        channel = message.channel
        overwrites = channel.overwrites
        overwrites[channel.guild.default_role] = discord.PermissionOverwrite(send_messages=False)
        await channel.edit(overwrites=overwrites)
        
        # Now let's alert the channel affected
        embed = self.bot.Embed(
            title='Mass Ping Found!',
            description='It seems an anauthorized user was able to ping @everyone or @here in this channel. '
                        'We\'re very sorry for the inconvience, I\'ll be locking this channel down in the '
                        'meant time until we can resolve this issue.',
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name='Actions Taken', value='This channel has been locked until further notice.'
                                                'The member in question has been placed in lockdown.')
        await message.channel.send(embed=embed)

        # Now let's send it to the member
        embed = self.bot.Embed(
            title=f'You Pinged {message.guild.member_count} people...',
            description=f'You have pinged @everyone or @here in {message.channel.mention}. This is not allowed.'
                        'I\'ve placed you in Lockdown until further notice.'
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name='Message Content', value=discord.utils.escape_mentions(message.content))
        await self.send_to(message.author, embed=embed)
        
        # Now let's send to logging channel.
        embed = self.bot.Embed(
            title=f'{message.author} was able to ping @here or @everyone.',
            description=f'{message.author.mention} was able to ping @here or @everyone in {message.channel.mention}'
        )
        embed.add_field(name='Message Content', value=discord.utils.escape_mentions(message.content))
        await self.bot.send_to_logging_channel(embed=embed)
        
    @commands.Cog.listener('on_message')
    async def file_checker(self, message: discord.Message):
        """|coro|
        
        Used to check for message attachments. Any message that has them is deleted without correct perms."""
        if should_ignore(message.author) or message.webhook_id:
            return
        
        if not message.attachments:
            return
        
        await message.delete()
        files = []
        for a in message.attachments:
            try:
                file = await a.to_file(use_cached=True)
            except:
                continue
            else:
                files.append(file)
                
        embed = self.bot.Embed(
            title='Message attachments found',
            description='Please do not post files!'
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.set_footer(text=f'Message ID: {message.id}')
        await message.channel.send(embed=embed)
        
        embed.description = f'{message.author.mention} has posted an attachment in {message.channel.mention}\n\nI have attached the files for you to view.'
        if len(files) == 1:
            file = files[0]
            embed.set_image(url=f'attachment://{file.filename}')
            return await self.bot.send_to_logging_channel(embed=embed, file=file)
            
        await self.bot.send_to_logging_channel(embed=embed, files=files)
        
    @commands.Cog.listener('on_message')
    async def message_content_check(self, message: discord.Message):
        """Used to determine if a message's content legnth is too high.
        
        Anything 700 or over will automatically be deleted."""
        if should_ignore(message.author) or message.webhook_id:
            return
        
        if not len(message.clean_content) >= 700:
            return
        
        await message.delete()
    
        embed = self.bot.Embed(
            title='Oh no!',
            description='Please do not post messages that long!'
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.set_footer(text=f'Message ID: {message.id}')
        return await message.channel.send(embed=embed, content=message.author.mention)
        
    @commands.Cog.listener('on_message_edit')
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Used to check if a member edited a message that now contains links / profanity.
        
        Parameters
        ---------
        before: :class:`Message`
            The message before its edit.
        after: :class:`discord.Message`
            The message after its edit.
        
        Returns
        -------
        None
        """
        if before.clean_content == after.clean_content:
            return
        
        self.bot.loop.create_task(self.profanity_checker(after))
        self.bot.loop.create_task(self.link_checker(after))
                    
    @commands.Cog.listener('on_message')
    async def profanity_checker(self, message: discord.Message) -> None:
        """Used to check if a message contains profanity.
        
        Parameters
        ----------
        message: :class:`discord.Message`
            The message to check.
        
        Returns
        -------
        None
        """
        if not message.guild or should_ignore(message.author) or message.webhook_id:
            return
        
        censored = self.bot.censor_message(message.content)
        if censored.lower() == message.content.lower():
            return
        
        await message.delete()
        
        await self.bot.lockdown_for(5*60, member=message.author, reason=Reasons.profanity)
        
        embed = self.bot.Embed(
            title='Oh no!',
            description='You can not use a message that contains profanity!\n\nI have locked you out of the server for 5 minutes. ' \
                'You will automatically be unlocked once that time is up.'
        )
        embed.add_field(name='Message:', value=message.content)
        embed.add_field(name='Censored:', value=censored)
        await self.bot.send_to(message.author, embed=embed)
        
        embed.title = 'Profanity Found'
        embed.description = f'{message.author.mention} has said a word that contains profanity in {message.channel.mention}.'
        embed.add_field(name='Action Taken', value='I have locked them out of the server for 5 minutes.')
        await self.bot.send_to_logging_channel(embed=embed)
        
    @commands.Cog.listener('on_message')
    async def link_checker(self, message: discord.Message) -> None:
        """Used to check if a message contains links in non-valid gif channels.
        
        Parameters
        ----------
        message: :class:`discord.Message`
            The message to check.
        
        Returns
        -------
        None
        """
        if not message.guild or should_ignore(message.author) or message.webhook_id:
            return
        
        if not (await self.bot.contains_links(message.clean_content)):
            return
        
        links = await self.bot.get_links(message.clean_content)
        valid = True
        
        for link in links:
            if not await self.bot.is_valid_link(link):
                valid = False
                await message.delete()
                break
        
        if valid is True:
            return
        
        e = self.bot.Embed(
            title='Oh no!',
            description="Links are not enabled in this server!"
        )
        e.add_field(name="Why aren't links enabled?", value='Due to FLVS Fury being a School Discord, we limit links to keep the server as PG as possible!')
        e.add_field(name='Invalid Links', value=', '.join(links))
        await self.bot.send_to(message.author, embed=e)
        
        # I'm creating a new embed here because I wont want to handle removing fields 
        # from the previous embed.
        e = self.bot.Embed(
            title='Link detected',
            description=f'{message.author.mention} has posted a link in {message.channel.mention}!'
        )
        e.add_field(name='Invalid Links', value=', '.join(links))
        await self.bot.send_to_logging_channel(embed=e)
        
    @commands.Cog.listener('on_user_update')
    async def user_username_update(self, before: discord.User, after: discord.User) -> None:
        """Checks when users update their usernames for profanity.
        
        Parameters
        ----------
        before: :class:`discord.User`
            The user before the update.
        after: :class:`discord.User`
            The user after the update.
            
        Returns
        -------
        None
        """
        if before.name == after.name:
            return
        
        if self.bot.contains_profanity(after.name):
            guild = self.bot.get_guild(constants.FURY_GUILD)
            member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
            await self.bot.lockdown(member, reason=Reasons.displayname)
        else:
            if await self.bot.is_locked(after):
                guild = self.bot.get_guild(constants.FURY_GUILD)
                member = guild.get_member(after.id) or (await guild.fetch_member(after.id))
                await self.bot.freedom(member, reason=Reasons.displayname) 

    @tasks.loop(count=1)
    async def name_checker(self) -> None:
        """Used to pool members and check for bad names and activities.
        
        .. note::
        
            This only gets called once, when the bot comes online.
        
        Returns
        -------
        None
        """
        guild = self.bot.get_guild(constants.FURY_GUILD)
        
        async for member in guild.fetch_members(limit=None):
            if (censored := self.bot.censor_message(member.display_name)) != member.display_name:
                await self.bot.lockdown(member, reason=Reasons.displayname)
                
                e = self.bot.Embed(
                    title='Lockdown Incoming!',
                    description=f'Member {member.mention} has been locked down for {Reasons.type_to_string(Reasons.displayname)}'
                )
                e.add_field(name='Name:', value=member.display_name)
                e.add_field(name='Censored:', value=censored)
                await self.bot.send_to_logging_channel(embed=e)
                
            if member.activities:
                activity = discord.utils.find(lambda activity: isinstance(activity, discord.CustomActivity), member.activities)
                if activity and activity.name:
                    if (censored := self.bot.censor_message(activity.name)) != activity.name:
                        await self.bot.lockdown(member, reason=Reasons.activity)
                        
                        e = self.bot.Embed(
                            title='Bad Status Found',
                            description=f'{member.mention} has been locked down for a bad status.'
                        )
                        e.add_field(name='Status', value=activity.name)
                        e.add_field(name='Censored', value=censored)
                        await self.bot.send_to_logging_channel(embed=e)
        
        log.info('Name Checker Finished.')
                
                
    @name_checker.before_loop
    async def name_checker_before_loop(self) -> None:
        log.info('Waiting for name checker...')
        await self.bot.wait_until_ready()
        log.info('Name checker started.')
        
    @tasks.loop(count=1)
    async def load_profanity(self) -> None:
        log.info("Loading profanity wordset now.")
        await self.bot.load_clean_words()
        await self.bot.load_dirty_words()
        log.info("Finished loading profanity wordset.")
        
def setup(bot):
    return bot.add_cog(Safety(bot))