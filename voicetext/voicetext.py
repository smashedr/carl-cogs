import discord
import logging
from datetime import datetime
from typing import Optional, Union, Dict

from redbot.core import commands, app_commands, Config
from redbot.core.bot import Red
from redbot.core.utils import chat_formatting as cf

from .converters import CarlChannelConverter

log = logging.getLogger('red.voicetext')


class VoiceText(commands.Cog):
    """Carl's VoiceText Cog"""

    guild_default = {
        'enabled': False,
        'secret': True,
        'archive': 0,
        'channels': [],
        'categories': [],
    }
    channel_default = {
        'text': 0,
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_channel(**self.channel_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member,
                                    part: discord.member.VoiceState,
                                    join: discord.member.VoiceState):
        if member.bot:
            log.debug('bot')
            return
        config: dict = await self.config.guild(member.guild).all()
        if not config['enabled']:
            log.debug('Guild Disabled')
            return

        if join.channel:
            log.debug('join.channel.name: %s', join.channel.name)
            await self.process_join(join.channel, member, config)
        if part.channel:
            log.debug('part.channel.name: %s', part.channel.name)
            await self.process_part(part.channel, member)

    @commands.hybrid_group(name='voicetext', aliases=['vt'], description='Voice Text Commands')
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin()
    async def vt(self, ctx: commands.Context):
        """Voice Text Commands"""

    @vt.command(name='ignore', aliases=['i'],
                description='Ignore a VoiceChannel or Category from VoiceText Creation')
    @app_commands.describe(name='VoiceChannel or Category to be Ignored')
    async def vt_ignore(self, ctx: commands.Context, name: CarlChannelConverter):
        """Ignore a VoiceChannel or Category from VoiceText Creation"""
        name: Union[discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel]
        log.debug('vt_ignore')
        log.debug('name: %s', name)
        if name.type == 'category':
            categories: list = await self.config.guild(ctx.guild).categories()
            if name.id in categories:
                categories.append(name.id)
                await self.config.guild(ctx.guild).categories.set(categories)
        if name.type == 'voice':
            channels: list = await self.config.guild(ctx.guild).categories()
            if name.id in channels:
                channels.append(name.id)
                await self.config.guild(ctx.guild).categories.set(channels)
        msg = f'\U00002705 {name.type.title()} `{name}` now ignored from VoiceText creation.'  # ✅
        await ctx.send(msg, ephemeral=True)

    @vt.command(name='unignore', aliases=['u'],
                description='Unignore a VoiceChannel or Category from VoiceText Creation')
    @app_commands.describe(name='VoiceChannel or Category to be Unignored')
    async def vt_unignore(self, ctx: commands.Context, name: CarlChannelConverter):
        """Unignore a VoiceChannel or Category from VoiceText Creation"""
        name: Union[discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel]
        log.debug('vt_unignore')
        log.debug('name: %s', name)
        if name.type == 'category':
            categories: list = await self.config.guild(ctx.guild).categories()
            if name.id not in categories:
                categories.remove(name.id)
                await self.config.guild(ctx.guild).categories.set(categories)
        if name.type == 'voice':
            channels: list = await self.config.guild(ctx.guild).categories()
            if name.id not in channels:
                channels.remove(name.id)
                await self.config.guild(ctx.guild).categories.set(channels)
        msg = f'\U00002705 {name.type.title()} `{name}` no longer ignored from VoiceText creation.'  # ✅
        await ctx.send(msg, ephemeral=True)

    @vt.command(name='archive', aliases=['a'],
                description='Archive Category for Ended Chats')
    @app_commands.describe(category='Set the Archive Category for Ended Chats')
    async def vt_archive(self, ctx: commands.Context, category: discord.CategoryChannel):
        """Set the Archive Category for Ended Chats"""
        category: discord.CategoryChannel
        log.debug('vt_archive')
        log.debug('name: %s', category)
        await self.config.guild(ctx.guild).archive.set(category.id)
        msg = f'\U00002705 Archive Category set to: {category.name}'  # ✅
        await ctx.send(msg, ephemeral=True)

    @vt.command(name='enable', aliases=['e', 'on'], description='Enable VoiceText in the Guild')
    async def vt_enable(self, ctx: commands.Context):
        """Enable VoiceText in the Guild"""
        log.debug('vt_enable')
        # enabled: bool = await self.config.guild(ctx.guild).enabled()
        config: dict = await self.config.guild(ctx.guild).all()
        log.debug('config: %s', config)
        if not config['archive']:
            msg = f'\U000026D4 Archive Category not set! To set: {ctx.clean_prefix}voicetext archive <category>'  # ⛔
            await ctx.send(msg, ephemeral=True)
            return

        if config['enabled']:
            await ctx.send('\U00002705 VoiceText is already enabled.', ephemeral=True)  # ✅
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('VoiceText has been enabled.', ephemeral=True)

    @vt.command(name='disable', aliases=['d', 'off'], description='Disable VoiceText in the Guild')
    async def vt_disable(self, ctx: commands.Context):
        """Disable VoiceText in the Guild"""
        log.debug('vt_disable')
        enabled: bool = await self.config.guild(ctx.guild).enabled()
        log.debug('enabled: %s', enabled)
        if not enabled:
            await ctx.send('\U00002705 VoiceText is already disabled.', ephemeral=True)
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('\U00002705 VoiceText has been disabled.', ephemeral=True)

    @vt.command(name='status', aliases=['s', 'settings'], description='Show VoiceText Status in Guild')
    async def vt_status(self, ctx: commands.Context):
        """Show VoiceText Status in Guild"""
        log.debug('vt_status')
        config: dict = await self.config.guild(ctx.guild).all()
        log.debug(config)
        #  ✅  ⛔
        is_enabled = '\U00002705 Enabled' if config['enabled'] else '\U000026D4 Disabled'
        archive = ctx.guild.get_channel(config['archive']) if config['archive'] else None
        msg = (
            f"**VoiceText Settings:**\n"
            f"Guild Status: {is_enabled}\n"
            f"Archive Category: {archive}\n"
            f"Ignored Channels: {cf.humanize_list(config['channels'])}\n"
            f"Ignored Categories: {cf.humanize_list(config['categories'])}"
        )
        await ctx.send(msg, ephemeral=True)

    async def process_join(self, channel, member: discord.Member, config: dict) -> None:
        channel: Union[discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel]
        if channel.id in config['channels']:
            log.debug('Channel "%s" is in Disabled', channel.name)
            return
        if channel.category:
            if channel.category.id in config['categories']:
                log.debug('Channel "%s" is in Disabled Category "%s"', channel.name, channel.category.name)
                return
        text_id: Optional[int] = await self.config.channel(channel).text()
        if text_id:
            text: discord.TextChannel = member.guild.get_channel(text_id)
            log.debug('Adding Member "%s" to TextChannel "%s"', member.name, text.name)
            await text.set_permissions(member, overwrite=discord.PermissionOverwrite(view_channel=True))
            return

        name = f"{channel.name.replace(' ', '-').lower()}-{datetime.strftime(datetime.now(), '%y%m%d-%H%M')}"
        log.debug(
            "Will create TextChannel '%s' for VoiceChannel: '%s' "
            "in Category: '%s' ", name, channel.name, channel.category.name
        )
        everyone: discord.Role = member.guild.get_role(member.guild.id)
        overwrites: Dict[discord.Member, discord.PermissionOverwrite] = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True),
        }
        text: discord.TextChannel = await member.guild.create_text_channel(
            name=name,
            overwrites=overwrites,
            category=channel.category,
            reason='VoiceText Auto Channel.',
            topic=f'Text Chat for Voice Channel {channel.name}',
        )
        await self.config.channel(channel).text.set(text.id)

    async def process_part(self, channel, member: discord.Member):
        channel: Union[discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel]
        if channel.members:
            log.debug('Channel Not Empty')
            return

        text_id: Optional[int] = await self.config.channel(channel).text()
        if text_id:
            text: discord.TextChannel = member.guild.get_channel(text_id)
            await self.config.channel(channel).clear()
            archive_id: int = await self.config.guild(member.guild).archive()
            archive: discord.CategoryChannel = member.guild.get_channel(archive_id)
            # await text.delete()  # TODO: This will archive the channel instead
            await text.move(end=True, category=archive)
            log.debug('channel archived: %s', text_id)
