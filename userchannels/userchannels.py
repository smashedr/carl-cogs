import discord
import logging
import random
from redbot.core import commands, Config

logger = logging.getLogger('red.userchannels')

ROOM_NAMES = {
    'a': ['Abode', 'Area'],
    'b': ['Bistro'],
    'c': ['Camp', 'Castle', 'Chamber', 'Crib'],
    'd': ['Dorm', 'Digs', 'Den'],
    'e': ['Encampment'],
    'f': ['Firehouse'],
    'gg': [''],
    'h': ['Hall', 'Harbor', 'Haven', 'Hotel', 'House'],
    'i': ['Inn'],
    'j': ['Joint'],
    'kk': [''],
    'l': ['Lodge'],
    'm': ['Motel', 'Mansion'],
    'n': ['Nest'],
    'oo': [''],
    'p': ['Pad', 'Paradise', 'Place', 'Pub'],
    'qq': ['Quarters'],
    'r': ['Range', 'Resort'],
    's': ['Square', 'Shack', 'Shelter', 'Startup'],
    't': ['Tent', 'Tower', 'Town'],
    'uu': [''],
    'v': ['Valley'],
    'ww': [''],
    'xx': [''],
    'yy': [''],
    'zz': [''],
}

GUILD_SETTINGS = {
    'enabled': False,
    'channel': None,
    'category': None,
}

CHANNEL_SETTINGS = {
    'auto': False,
    'owner': None,
}


class Userchannels(commands.Cog):
    """Carl's Userchannels Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**GUILD_SETTINGS)
        self.config.register_channel(**CHANNEL_SETTINGS)

    async def initialize(self) -> None:
        logger.info('Initializing Userchannels Cog')

    async def process_remove(self, channel):
        if channel.members:
            logger.debug('Channel Not Empty')
            return
        if not await self.config.channel(channel).auto():
            logger.debug('Channel Not Autochannel')
            return

        try:
            channel_id = channel.id
            await channel.delete(reason='Userchannels channel empty.')
            logger.info('Removed Channel %s', channel_id)
        except discord.NotFound:
            logger.debug('Channel Not Found')

        await self.config.channel(channel).clear()
        logger.debug('Database Cleared')

    async def process_user_create(self, channel, member):
        config = await self.config.guild(member.guild).all()

        # get category
        dest_category = member.guild.get_channel(config['category'])

        # get channel name
        suffix = 'Room'
        if member.display_name[0].lower() in ROOM_NAMES:
            suffix = random.choice(ROOM_NAMES[member.display_name[0].lower()])
        channel_name = f"{member.display_name}'s {suffix}"
        logger.debug(channel_name)

        # create channel
        overwrites = {
            'connect': True,
            'create_instant_invite': True,
            'deafen_members': True,
            'manage_channels': True,
            'manage_permissions': True,
            'move_members': True,
            'mute_members': True,
            'speak': True,
            'stream': True,
        }
        voice_channel = await member.guild.create_voice_channel(
            name=channel_name,
            category=dest_category,
            reason='Userchannels autocreated channel.',
            user_limit=99,
            bitrate=96000,
            # overwrites=overwrites,
        )
        await self.config.channel(voice_channel).auto.set(True)
        await self.config.channel(voice_channel).owner.set(member.id)
        logger.debug('Created Channel')

        # move member
        await member.move_to(voice_channel, reason='Userchannels moving user.')
        logger.debug('Moved Member')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, part, join):
        if member.bot:
            logger.debug('bot')
            return

        config = await self.config.guild(member.guild).all()
        if not config['enabled']:
            logger.debug('disabled')
            return

        if join.channel:
            if config['channel'] == join.channel.id:
                logger.debug('user channel join')
                await self.process_user_create(join.channel, member)

        if part.channel:
            if await self.config.channel(part.channel).auto():
                logger.debug('auto channel part')
                await self.process_remove(part.channel)

    @commands.group(name='userchannels', aliases=['uc'])
    @commands.guild_only()
    @commands.admin()
    async def userchannels(self, ctx):
        """Options for managing Userchannels."""

    @userchannels.command(name='enable', aliases=['e', 'on'])
    async def userchannels_enable(self, ctx):
        """Enable Userchannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Userchannels is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Userchannels has been enabled.')

    @userchannels.command(name='disable', aliases=['d', 'off'])
    async def userchannels_disable(self, ctx):
        """Disable Userchannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Userchannels is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Userchannels has been disabled.')

    @userchannels.command(name='channel', aliases=['ch', 'chan', 'chann'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def userchannels_channel(self, ctx, *, channel: discord.VoiceChannel):
        """Set Userchannels Userchannels channel."""
        logger.debug(channel.id)
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f'Userchannels Userchannels Channel set to:\n'
                       f'**{channel.name}** - {channel.id}')

    @userchannels.command(name='category', aliases=['ca', 'cat'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def userchannels_category(self, ctx, *, category: discord.CategoryChannel):
        """Set Userchannels Userchannels category."""
        logger.debug(category.id)
        await self.config.guild(ctx.guild).category.set(category.id)
        await ctx.send(f'Userchannels Userchannels Category set to:\n'
                       f'**{category.name}** - {category.id}')

    @userchannels.command(name='status', aliases=['s', 'stat', 'settings'])
    async def userchannels_status(self, ctx):
        """Get Userchannels Userchannels status."""
        config = await self.config.guild(ctx.guild).all()
        logger.debug(config)
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        channel = ctx.guild.get_channel(config['channel'])
        category = ctx.guild.get_channel(config['category'])
        out = f'Userchannels Userchannels Settings:\n' \
              f'Global Enabled: {status}\n' \
              f'Users Channel: {channel}\n' \
              f'Users Category: {category}'
        await ctx.send(out)
