import discord
import logging
from typing import Optional, Union

from discord.ext import tasks
from redbot.core import Config, checks, commands

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
        # for emoji, _ in maps:
        #     emoji = await self._get_emoji(message.guild, emoji_type)
        #     await message.add_reaction(emoji_tuple[0])

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions added to a message."""
        log.debug('payload: %s', payload)
        log.debug('payload.emoji: %s', payload.emoji)
        member = payload.member
        if not member or member.bot:
            return
        if not payload.guild_id or payload.channel_id or payload.message_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channels: list = await self.config.guild(guild).channels()
        if payload.channel_id not in channels:
            return
        channel = guild.get_channel(payload.channel_id)
        if not channel:
            log.error('404 - Channel Not Found: %s', payload.channel_id)
            return

        log.debug('payload: %s', payload)
        log.debug('payload.emoji: %s', payload.emoji)

    def get_emoji_react(self, emoji) -> Optional[Union[discord.Emoji, str]]:
        try:
            if isinstance(emoji, discord.Emoji):
                return emoji
            if isinstance(emoji, str) and not emoji.isdigit():
                return emoji.encode('unicode-escape').decode('ASCII')
            if isinstance(emoji, int) or emoji.isdigit():
                return self.bot.get_emoji(int(emoji))
        except Exception as error:
            log.error(error)
            return None

    @staticmethod
    def get_emoji_id(emoji) -> Optional[Union[str, int]]:
        try:
            if isinstance(emoji, discord.Emoji):
                return emoji.id
            if isinstance(emoji, str) and not emoji.isdigit():
                return emoji.encode('unicode-escape').decode('ASCII')
            if isinstance(emoji, int) or emoji.isdigit():
                return int(emoji)
        except Exception as error:
            log.error(error)
            return None

    @commands.group(name='reactpost', aliases=['react', 'rp'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def _rp(self, ctx):
        """Manage the ReactPost Options"""

    @_rp.command(name='addmap', aliases=['a', 'amap'])
    async def _rp_addmap(self, ctx: commands.Context,
                         emoji: Union[discord.Emoji, discord.PartialEmoji, str],
                         channel: discord.TextChannel):
        """Add Emoji to Channel Mapping"""
        log.debug('channel: %s', channel)
        log.debug('emoji: %s', emoji)
        log.debug('str(emoji): %s', str(emoji))
        log.debug('type(emoji): %s', type(emoji))
        log.debug('-'*40)
        emoji = self.get_emoji_id(emoji)
        log.debug('emoji ID: %s', emoji)

        maps: dict = await self.config.guild(ctx.guild).maps()
        log.debug('maps: %s', maps)
        if emoji in maps:
            map_channel = ctx.guild.get_channel(maps[emoji])
            if map_channel:
                await ctx.send(f'⛔ Emoji {self.get_emoji_react(emoji)} already mapped to {channel.mention}')
                return
        maps[emoji] = channel.id
        log.debug('maps: %s', maps)
        await self.config.guild(ctx.guild).maps.set(maps)
        await ctx.send(f'✅ Mapped Emoji {emoji} to post to channel {channel.mention}')

    @_rp.command(name='removemap', aliases=['r', 'rmap'])
    async def _rp_removemap(self, ctx: commands.Context, emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Remove Emoji to Channel Mapping"""
        log.debug('emoji: %s', emoji)
        maps: dict = await self.config.guild(ctx.guild).maps()
        log.debug('maps: %s', maps)
        # if emoji.id not in maps:
        #     await ctx.send(f'⛔ Emoji {emoji} is not mapped to any channel.')
        #     return
        # channel = ctx.guild.get_channel(maps[emoji.id])
        # del maps[emoji.id]
        # log.debug('maps: %s', maps)
        # await self.config.guild(ctx.guild).maps.set(maps)
        # await ctx.send(f'✅ Removed Emoji {emoji} mapped to channel {channel.mention}')

    @_rp.command(name='enable', aliases=['e', 'on'])
    async def _rp_enable(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Enables ReactPost in the current channel or <channel>"""
        channel: discord.TextChannel = channel if channel else ctx.channel
        log.debug('channel: %s', channel)
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
        channels: list = await self.config.guild(ctx.guild).channels()
        log.debug('channels: %s', channels)
        if channel.id in channels:
            await ctx.send(f'⛔ Channel {channel.mention} already Enabled.')
            return
        channels.remove(channel.id)
        log.debug('channels: %s', channels)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'✅ Enabled Channel {channel.mention}')
