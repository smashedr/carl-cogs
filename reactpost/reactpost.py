import discord
import logging
from typing import Optional, Union

from discord.ext import tasks
from redbot.core import Config, checks, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.reactpost')


class ReactPost(commands.Cog):
    """Custom ReactPost Cog."""

    guild_default = {
        'channels': [],
        'maps': {},
    }
    # channel_default = {
    #     'enabled': False,
    # }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        # self.config.register_channel(**self.channel_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)
        self.main_loop.start()

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=30.0)
    async def main_loop(self):
        log.info('%s: Main Loop Task Run', self.__cog_name__)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Watch for messages in enabled react channels to add reactions."""
        guild = message.guild
        channel = message.channel
        if not guild or not channel:
            return
        channels: list = await self.config.guild(guild).channels()
        if channel.id not in channels:
            return
        if not channel.permissions_for(message.guild.me).add_reactions:
            log.error('Can not react in channel: %s - %s', message.channel.id, message.channel.name)
            return

        maps: dict = await self.config.guild(guild).maps()
        log.debug('maps: %s', maps)
        for emoji, _ in maps.items():
            # emoji = await self._get_emoji(message.guild, emoji_type)
            await message.add_reaction(emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions added to a message."""
        member: discord.Member = payload.member
        if not member or member.bot:
            log.debug(0)
            return
        if not payload.guild_id or not payload.channel_id or not payload.message_id:
            log.debug(1)
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            log.debug(2)
            return
        channels: list = await self.config.guild(guild).channels()
        if payload.channel_id not in channels:
            log.debug(3)
            return
        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        if not channel:
            # TODO: channel deleted, remove from config: channels
            log.error('404 - Channel Not Found: %s', payload.channel_id)
            return
        maps: dict = await self.config.guild(guild).maps()
        log.debug('maps: %s', maps)
        if str(payload.emoji) not in maps:
            log.debug(5)
            return
        destination: discord.TextChannel = guild.get_channel(maps[str(payload.emoji)])
        if not destination:
            # TODO: mapping channel deleted, remove from config: maps
            log.error('404 - Channel Not Found: %s', maps[str(payload.emoji)])
            return

        log.debug('payload.emoji: %s', payload.emoji)
        message: discord.Message = await channel.fetch_message(payload.message_id)
        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file())
        embeds = [e for e in message.embeds if e.type == 'rich']
        await destination.send(message.content, embeds=embeds, files=files)

    @commands.group(name='reactpost', aliases=['react', 'rp'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def _rp(self, ctx):
        """Manage the ReactPost Options"""

    @_rp.command(name='addmap', aliases=['a', 'amap'])
    async def _rp_addmap(self, ctx: commands.Context,
                         emoji: Union[discord.Emoji, discord.PartialEmoji, str],
                         channel: discord.TextChannel):
        """Add Emoji to a Channel Mapping"""
        log.debug('emoji: %s', emoji)
        log.debug('channel: %s', channel)
        maps: dict = await self.config.guild(ctx.guild).maps()
        log.debug('maps: %s', maps)
        if emoji in maps:
            map_channel = ctx.guild.get_channel(maps[str(emoji)])
            if map_channel:
                await ctx.send(f'⛔ Emoji {emoji} already mapped to {channel.mention}')
                return
        maps[str(emoji)] = channel.id
        log.debug('maps: %s', maps)
        await self.config.guild(ctx.guild).maps.set(maps)
        await ctx.send(f'✅ Mapped Emoji {emoji} to post to channel {channel.mention}')

    @_rp.command(name='removemap', aliases=['r', 'rmap'])
    async def _rp_removemap(self, ctx: commands.Context, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Remove Emoji from a Channel Mapping"""
        log.debug('emoji: %s', emoji)
        maps: dict = await self.config.guild(ctx.guild).maps()
        log.debug('maps: %s', maps)
        if str(emoji) not in maps:
            await ctx.send(f'⛔ Emoji {emoji} is not mapped to any channel.')
            return
        channel = ctx.guild.get_channel(maps[str(emoji)])
        del maps[str(emoji)]
        log.debug('maps: %s', maps)
        await self.config.guild(ctx.guild).maps.set(maps)
        await ctx.send(f'✅ Removed Emoji {emoji} mapped to channel {channel.mention}')

    @_rp.command(name='enable', aliases=['e', 'on'])
    async def _rp_enable(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Enables ReactPost in the current channel or <channel>"""
        channel: discord.TextChannel = channel if channel else ctx.channel
        log.debug('channel: %s', channel)
        log.debug('channel.id: %s', channel.id)
        channels: list = await self.config.guild(ctx.guild).channels()
        log.debug('channels: %s', channels)
        if channel.id in channels:
            await ctx.send(f'⛔ Channel {channel.mention} already Enabled.')
            return
        channels.append(channel.id)
        log.debug('channels: %s', channels)
        await self.config.guild(ctx.guild).channels.set(channels)
        await ctx.send(f'✅ Enabled Channel {channel.mention}')

    @_rp.command(name='disable', aliases=['d', 'off'])
    async def _rp_disable(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Disable ReactPost in the current channel or <channel>"""
        channel: discord.TextChannel = channel if channel else ctx.channel
        log.debug('channel: %s', channel)
        log.debug('channel.id: %s', channel.id)
        channels: list = await self.config.guild(ctx.guild).channels()
        log.debug('channels: %s', channels)
        if channel.id not in channels:
            await ctx.send(f'⛔ Channel {channel.mention} already Disabled.')
            return
        channels.remove(channel.id)
        log.debug('channels: %s', channels)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'✅ Disabled Channel {channel.mention}')

    @_rp.command(name='status', aliases=['s', 'mapping', 'maps'])
    async def _rp_status(self, ctx: commands.Context):
        """Status of ReactPost Channels and Mapped Channels"""
        config: dict = await self.config.guild(ctx.guild).all()
        log.debug('maps: %s', config['maps'])
        log.debug('channels: %s', config['channels'])
        channels = []
        for channel_id in config['channels']:
            channel = ctx.guild.get_channel(channel_id)
            channels.append(channel.mention)
        mappings = []
        for emoji, channel_id in config['maps'].items():
            log.debug('emoji: %s', emoji)
            log.debug('channel_id: %s', channel_id)
            channel = ctx.guild.get_channel(channel_id)
            mappings.append(f'{emoji} -> {channel.mention}')
        mappings = '\n'.join(mappings) if mappings else 'No Mappings.'
        channels = cf.humanize_list(channels) if channels else 'No Channels.'
        msg = (
            f'_ReactPost Settings._\n**Enabled Channels:**\n'
            f'{channels}\n\n'
            f'**Mappings:**\n'
            f'{mappings}'
        )
        log.debug('msg: %s', msg)
        await ctx.send(msg)
