import datetime
import discord
import logging
from typing import Optional, Union, Tuple, Dict, List

from discord.ext import tasks
from redbot.core import app_commands, commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.autoarchive')


class Autoarchive(commands.Cog):
    """Carl's Autoarchive Cog"""

    # TODO: Make these config options
    archive_category = 'Auto-Archive'
    move_messages = 50

    guild_default = {
        'channels': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        self.main_loop.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=120.0)
    async def main_loop(self):
        await self.bot.wait_until_ready()
        log.info('%s: Run Loop: main_loop', self.__cog_name__)
        all_guilds: dict = await self.config.all_guilds()
        log.debug('all_guilds: %s', all_guilds)
        for guild_id, data in await AsyncIter(all_guilds.items(), delay=5, steps=10):
            log.debug('guild_id: %s', guild_id)
            if not data['channels']:
                continue
            guild: discord.Guild = self.bot.get_guild(guild_id)
            log.info('Processing Guild: %s: %s', guild.id, guild.name)
            for channel_id in data['channels']:
                channel: discord.TextChannel = guild.get_channel(channel_id)
                log.info('Processing Channel: %s - %s', channel.id, channel.name)
                count = 0
                async for _ in channel.history(limit=None):
                    count += 1
                if count > 9000:
                    log.info('Archiving Channel: %s: %s', channel.id, channel.name)
                    await self.archive_channel(channel)

    async def archive_channel(self, channel: discord.TextChannel) -> None:
        guild = channel.guild
        archive: discord.CategoryChannel = discord.utils.get(guild.channels, name=self.archive_category)
        if not archive:
            await guild.create_category_channel(name=self.archive_category, reason='Auto Archive Category')
        if not archive.type == 'category':
            # TODO: Process Error
            log.error('Archive Channel is not a Category: %s: %s', archive.id, archive.name)
            return

        # clone channel and position
        clone = await channel.clone()
        await clone.edit(position=channel.position)

        # move to archive category
        await channel.edit(category=archive)

        # update old channel permissions
        permissions = discord.PermissionOverwrite(send_messages=False)
        everyone: discord.Role = guild.get_role(guild.id)
        overwrites = {everyone: permissions}
        await channel.edit(overwrites=overwrites)

        # move webhooks to new channel
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            await webhook.edit(channel=clone)

        # send embed to old channel
        embed = discord.Embed(
            title=f'Replacement Channel Created #{channel.name}',
            url=clone.jump_url,
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(
            name=f'#{clone.name}',
            url=clone.jump_url,
        )
        embed.description = (
            '**Channel Archived to Preserve History**\n\n'
            'Discord limits channels to 10,000 messages. '
            'To preserve the message history, '
            'this channel has been archived; however,  '
            f'a [new channel]({clone.jump_url}) '
            'has been created to replace this one.\n\n'
            f'**[Go To New Channel...]({clone.jump_url})**'
        )
        embed.set_thumbnail(url='https://img.cssnr.com/p/20230611-182505549.png')
        await channel.send(embed=embed, silent=True)

        # send embed to new channel
        embed = discord.Embed(
            title=f'Original Channel History #{channel.name}',
            url=channel.jump_url,
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(),
        )
        embed.set_author(
            name=f'#{channel.name}',
            url=channel.jump_url,
        )
        embed.description = (
            '**Channel Archived to Preserve History**\n\n'
            'Discord limits channels to 10,000 messages. '
            'To preserve the message history, '
            'this channel has been archived; however,  '
            f'the [old channel]({channel.jump_url}) '
            'is still available to view history.\n\n'
            f'**[Go To Original Channel...]({channel.jump_url})**'
        )
        embed.set_thumbnail(url='https://img.cssnr.com/p/20230611-182505549.png')
        await channel.send(embed=embed, silent=True)

        # move last X messages via webhook
        messages: List[discord.Message] = []
        async for message in channel.history(limit=self.move_messages):
            log.info('message: %s', message.content)
            messages.append(message)
        hook: discord.Webhook = await clone.create_webhook(name='AutoArchive', reason='Auto Archive Recent History')
        async for message in AsyncIter(reversed(messages), delay=2, steps=25):
            user: discord.Member = message.author
            files: List[discord.File] = []
            for attachment in message.attachments:
                files.append(await attachment.to_file())
            embeds: List[discord.Embed] = [e for e in message.embeds if e.type == 'rich']
            await hook.send(
                username=user.display_name or user.name,
                avatar_url=user.avatar.url,
                content=message.content,
                embeds=embeds,
                files=files,
                silent=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        await hook.delete(reason='Auto Archive Recent History')

    @commands.group(name='autoarchive', aliases=['aa'])
    @commands.guild_only()
    @commands.admin()
    async def _aa(self, ctx: commands.Context):
        """Options for managing Auto Archive."""

    @_aa.command(name='channels', aliases=['c', 'chan', 'chann', 'channel'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def _aa_channel(self, ctx: commands.Context):
        """Set Channels to Auto Archive"""
        view = ChannelView(self, ctx.author)
        msg = 'Select channels to **Auto Archive**:'
        await view.send_initial_message(ctx, msg, True)


class ChannelView(discord.ui.View):
    def __init__(self, cog, author: Union[discord.Member, discord.User, int],
                 timeout: int = 60 * 3, delete_after: int = 60):
        self.cog = cog
        self.user_id: int = author.id if hasattr(author, 'id') else int(author)
        self.delete_after: int = delete_after
        self.ephemeral: bool = False
        self.message: Optional[discord.Message] = None
        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx, message: Optional[str] = None,
                                   ephemeral: bool = False, **kwargs) -> discord.Message:
        self.ephemeral = ephemeral
        self.message = await ctx.send(content=message, view=self, ephemeral=self.ephemeral, **kwargs)
        return self.message

    async def on_timeout(self):
        await self.message.delete()
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.user_id:
            return True
        msg = f"\U000026D4 Looks like you did not create this response."  # ⛔
        await interaction.response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        return False

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text],
                       min_values=0, max_values=25)
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        response = interaction.response
        channels: List[app_commands.AppCommandChannel] = []
        for value in select.values:
            channels.append(value)
        if not channels:
            await self.cog.config.guild(interaction.guild).channels.set([])
            msg = f'\U00002705 No Channel Selected. Auto Archive Disabled.'  # ✅
            return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
        ids = [x.id for x in channels]
        await self.cog.config.guild(interaction.guild).channels.set(ids)
        names = [x.name for x in channels]
        msg = f'\U00002705 Auto Archive Enabled for Channels: {cf.humanize_list(names)}'  # ✅
        return await response.send_message(msg, ephemeral=True, delete_after=self.delete_after)
