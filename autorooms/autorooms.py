import discord
import logging
import random
from redbot.core import commands, Config

logger = logging.getLogger('red.autorooms')

DEFAULT_SETTINGS = {
    'enabled': False,
    'channel': None,
    'category': None,
    'rooms': None,
}

ROOM_NAMES = {
    'a': ['Area'],
    'b': ['Bistro'],
    'c': ['Camp', 'Castle', 'Chamber'],
    'd': ['Dorm', 'Digs'],
    'e': ['Encampment'],
    'f': ['Firehouse'],
    'g': ['Encampment'],
    'h': ['Hall', 'Hotel'],
    'i': ['Inn'],
    'j': ['Joint'],
    'kk': [''],
    'l': ['Lodge'],
    'm': ['Motel', 'Mansion'],
    'n': ['Nest'],
    'oo': [''],
    'p': ['Paradise', 'Place', 'Pub'],
    'qq': [''],
    'r': ['Range', 'Resort'],
    's': ['Square', 'Shack', 'Shelter', 'Startup'],
    't': ['Tent', 'Town'],
    'uu': [''],
    'v': ['Valley'],
    'ww': [''],
    'xx': [''],
    'yy': [''],
    'zz': [''],
}


class Autorooms(commands.Cog):
    """Carl's Autorooms Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**DEFAULT_SETTINGS)
        self.config.register_channel(enabled=False, owner=None)

    async def initialize(self) -> None:
        logger.info('Initializing Autorooms Cog')

    async def process_create(self, member):
        # get category
        config = await self.config.guild(member.guild).all()
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
            reason="Autorooms autocreated channel.",
            user_limit=99,
            bitrate=96000,
            # overwrites=overwrites,
        )
        await self.config.channel(voice_channel).enabled.set(True)
        await self.config.channel(voice_channel).owner.set(member.id)
        await member.move_to(
            voice_channel, reason="Autorooms moving user to new channel."
        )

        logger.debug('I did it!')

    async def process_remove(self, channel):
        if channel.members:
            logger.debug('Not Empty')
            return
        if await self.config.channel(channel).enabled():
            logger.debug('WILL REMOVE CHANNEL HERE!!!')
            await self.config.channel(channel).clear()
            try:
                await channel.delete(reason="Autorooms channel empty.")
            except discord.NotFound:
                logger.debug('Channel Not Found')
            logger.debug('I did it!')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, leaving, joining):
        logger.debug('member: %s', member)
        logger.debug('leaving: %s', leaving)
        logger.debug('joining: %s', joining)
        if member.bot:
            logger.debug('bot')
            return
        config = await self.config.guild(member.guild).all()
        if not config or not config['enabled']:
            logger.debug('disabled')
            return

        if joining.channel:
            logger.debug('joining')
            logger.debug(joining.channel.id)
            if joining.channel.id == config['channel']:
                logger.debug('PROCESS - joining')
                await self.process_create(member)

        if leaving.channel:
            logger.debug('PROCESS - leaving')
            await self.process_remove(leaving.channel)

    @commands.group(name='autorooms', aliases=['arr'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def autorooms(self, ctx):
        """Options for managing Autorooms."""

    @autorooms.command(name='enable', aliases=['on'])
    async def autorooms_enable(self, ctx):
        """Enables Autorooms."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Autorooms is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Autorooms has been enabled.')

    @autorooms.command(name='disable', aliases=['off'])
    async def autorooms_disable(self, ctx):
        """Disable Autorooms."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Autorooms is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Autorooms has been disabled.')

    @autorooms.command(name='channel')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autorooms_channel(self, ctx, *, channel: discord.VoiceChannel):
        """Set Autoroom channel."""
        logger.debug(channel.id)
        # channel = await self.config.guild(ctx.guild).channel()
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f'Autoroom Channel set to: **{channel.name}** - {channel.id}')

    @autorooms.command(name='category')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autorooms_category(self, ctx, *, category: discord.CategoryChannel):
        """Set Autoroom category."""
        logger.debug(category.id)
        # category = await self.config.guild(ctx.guild).category()
        await self.config.guild(ctx.guild).category.set(category.id)
        await ctx.send(f'Autoroom Category set to: **{category.name}** - {category.id}')

    @autorooms.command(name='status', aliases=['info', 'settings'])
    async def autorooms_status(self, ctx):
        """Get Autorooms status."""
        config = await self.config.guild(ctx.guild).all()
        logger.debug(config)
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        channel = ctx.guild.get_channel(config['channel'])
        category = ctx.guild.get_channel(config['category'])
        out = f'Autorooms Settings:\n' \
              f'Enabled: {status}\n' \
              f'Channel: {channel}\n' \
              f'Category: {category}'
        await ctx.send(out)
