import asyncio

import discord
import logging
from typing import Optional, Union, List, Dict

from redbot.core import Config, checks, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.reactpost')


class ReactPost(commands.Cog):
    """Custom ReactPost Cog."""

    guild_default = {
        'channels': [],
        'maps': {},
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        """Watch for messages in enabled channels to add reactions"""
        guild: discord.Guild = message.guild
        channel: discord.TextChannel = message.channel
        if not guild or not channel:
            return
        channels: List[str] = await self.config.guild(guild).channels()
        if channel.id not in channels:
            return
        if not channel.permissions_for(message.guild.me).add_reactions:
            log.error('Can not react in channel: %s - %s',
                      message.channel.id, message.channel.name)
            return

        maps: dict = await self.config.guild(guild).maps()
        # log.debug('maps: %s', maps)
        for emoji in maps:
            await message.add_reaction(emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Watch for reactions added to a message in an enabled channel"""
        if not payload.member or payload.member.bot:
            return
        if not payload.guild_id or not payload.channel_id or not payload.message_id:
            return
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        channels: List[int] = await self.config.guild(guild).channels()
        if payload.channel_id not in channels:
            return
        maps: Dict[str, int] = await self.config.guild(guild).maps()
        if str(payload.emoji) not in maps:
            return
        dest: discord.TextChannel = guild.get_channel(maps[str(payload.emoji)])
        if not dest:
            log.error('404 - Channel Not Found - Removing: %s', maps[str(payload.emoji)])
            del maps[str(payload.emoji)]
            await self.config.guild(guild).maps.set(maps)
            return

        channel: discord.TextChannel = guild.get_channel(payload.channel_id)
        message: discord.Message = await channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if isinstance(reaction.emoji, str):
                emoji_string = reaction.emoji
            else:
                emoji_string = reaction.emoji.name
            if emoji_string == payload.emoji.name:
                if reaction.count > 2:
                    await message.add_reaction('\U000026D4')
                    await asyncio.sleep(3.0)
                    await message.remove_reaction('\U000026D4', guild.me)
                    return

        files = []
        for attachment in message.attachments:
            files.append(await attachment.to_file())
        embeds: List[discord.Embed] = [e for e in message.embeds if e.type == 'rich']
        content = f'**ReactPost** from {message.jump_url} by {payload.member.mention}\n{message.content}'
        await dest.send(content, embeds=embeds, files=files)
        await message.add_reaction('\U00002705')
        await asyncio.sleep(3.0)
        await message.remove_reaction('\U00002705', guild.me)

    @commands.group(name='reactpost', aliases=['react', 'rp'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def _rp(self, ctx):
        """Manage the ReactPost Options"""

    @_rp.command(name='addmap', aliases=['a', 'add', 'amap'])
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
                await ctx.send(f'⛔ Emoji {emoji} already mapped to {channel.mention}',
                               ephemeral=True, delete_after=15)
                return
        maps[str(emoji)] = channel.id
        log.debug('maps: %s', maps)
        await self.config.guild(ctx.guild).maps.set(maps)
        await ctx.send(f'✅ Mapped Emoji {emoji} to post to channel {channel.mention}',
                       ephemeral=True, delete_after=60)

    @_rp.command(name='delmap', aliases=['d', 'del', 'dmap', 'deletemap'])
    async def _rp_delmap(self, ctx: commands.Context,
                         emoji: Union[discord.Emoji, discord.PartialEmoji, str]):
        """Delete Emoji from a Channel Mapping"""
        log.debug('emoji: %s', emoji)
        maps: dict = await self.config.guild(ctx.guild).maps()
        log.debug('maps: %s', maps)
        if str(emoji) not in maps:
            await ctx.send(f'⛔ Emoji {emoji} is not mapped to any channel.',
                           ephemeral=True, delete_after=15)
            return
        channel = ctx.guild.get_channel(maps[str(emoji)])
        del maps[str(emoji)]
        log.debug('maps: %s', maps)
        await self.config.guild(ctx.guild).maps.set(maps)
        await ctx.send(f'✅ Removed Emoji {emoji} mapped to channel {channel.mention}',
                       ephemeral=True, delete_after=60)

    @_rp.command(name='enable', aliases=['on'])
    async def _rp_enable(self, ctx: commands.Context,
                         channel: Optional[discord.TextChannel]):
        """Enables ReactPost in the current channel or <channel>"""
        channel: discord.TextChannel = channel if channel else ctx.channel
        log.debug('channel: %s', channel)
        channels: list = await self.config.guild(ctx.guild).channels()
        log.debug('channels: %s', channels)
        if channel.id in channels:
            await ctx.send(f'⛔ Channel {channel.mention} already Enabled.',
                           ephemeral=True, delete_after=15)
            return
        channels.append(channel.id)
        log.debug('channels: %s', channels)
        await self.config.guild(ctx.guild).channels.set(channels)
        await ctx.send(f'✅ Enabled Channel {channel.mention}',
                       ephemeral=True, delete_after=60)

    @_rp.command(name='disable', aliases=['off'])
    async def _rp_disable(self, ctx: commands.Context,
                          channel: Optional[discord.TextChannel]):
        """Disable ReactPost in the current channel or <channel>"""
        channel: discord.TextChannel = channel if channel else ctx.channel
        log.debug('channel: %s', channel)
        channels: list = await self.config.guild(ctx.guild).channels()
        log.debug('channels: %s', channels)
        if channel.id not in channels:
            await ctx.send(f'⛔ Channel {channel.mention} already Disabled.',
                           ephemeral=True, delete_after=15)
            return
        channels.remove(channel.id)
        log.debug('channels: %s', channels)
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send(f'✅ Disabled Channel {channel.mention}',
                       ephemeral=True, delete_after=60)

    @_rp.command(name='status', aliases=['s', 'maps', 'mapping', 'list'])
    async def _rp_status(self, ctx: commands.Context):
        """Status of ReactPost Channels and Mapped Channels"""
        config: dict = await self.config.guild(ctx.guild).all()
        log.debug('config: %s', config)
        channels = []
        for channel_id in config['channels']:
            channel = ctx.guild.get_channel(channel_id)
            channels.append(channel.mention)
        mappings = []
        for emoji, channel_id in config['maps'].items():
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
        await ctx.send(msg, ephemeral=True, delete_after=300)
