import discord
import logging
from redbot.core import commands, Config

logger = logging.getLogger('red.autochannels')


GUILD_SETTINGS = {
    'enabled': False,
    'channel': None,
}

CHANNEL_SETTINGS = {
    'room': False,
    'auto': False,
    'parent': None,
    'owner': None,
}


class Autochannels(commands.Cog):
    """Carl's Autochannels Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**GUILD_SETTINGS)
        self.config.register_channel(**CHANNEL_SETTINGS)

    async def initialize(self) -> None:
        logger.info('Initializing Autochannels Cog')

    async def process_remove(self, channel):
        if channel.members:
            logger.debug('Channel Not Empty')
            return
        if not await self.config.channel(channel).auto():
            logger.debug('Channel Not Autochannel')
            return

        try:
            await channel.delete(reason='Autochannels channel empty.')
            logger.debug('Channel Removed')
        except discord.NotFound:
            logger.debug('Channel Not Found')

        await self.config.channel(channel).clear()
        logger.debug('Database Cleared')

    async def process_autoroom_create(self, channel, member):
        # config = await self.config.guild(member.guild).all()
        config = await self.config.channel(channel).all()

        # get channel name
        if config['parent']:
            parent = member.guild.get_channel(config['parent'])

        # logger.debug(config)
        # member.guild.get_channel(channel.category)
        log = channel.category.channels
        logger.debug(dir(log))
        logger.debug(type(log))
        logger.debug(log)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, part, join):
        # logger.debug('member: %s', member)
        # logger.debug('part: %s', part)
        # logger.debug('join: %s', join)
        if member.bot:
            logger.debug('bot')
            return
        config = await self.config.guild(member.guild).all()
        if not config['enabled']:
            logger.debug('disabled')
            return

        if join.channel:
            if await self.config.channel(join.channel).room():
                logger.debug('autoroom channel join')
                await self.process_autoroom_create(join.channel, member)

        if part.channel:
            if await self.config.channel(part.channel).auto():
                logger.debug('auto channel part')
                await self.process_remove(part.channel)

    @commands.group(name='autochannels', aliases=['ac'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def autochannels(self, ctx):
        """Options for managing Autochannels."""

    @autochannels.command(name='enable', aliases=['e', 'on'])
    async def autochannels_enable(self, ctx):
        """Enable Autochannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Autochannels is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Autochannels has been enabled.')

    @autochannels.command(name='disable', aliases=['d', 'off'])
    async def autochannels_disable(self, ctx):
        """Disable Autochannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Autochannels is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Autochannels has been disabled.')

    @autochannels.command(name='add', aliases=['a'])
    async def autochannels_add(self, ctx, *, channel: discord.VoiceChannel):
        """
        Adds a channel to Autochannels Autorooms configuration.
        [p]autochannels add Channel Name
        """
        # log = category
        # logger.debug(dir(log))
        # logger.debug(type(log))
        # logger.debug(log)
        await ctx.send(f'Autochannel Autorooms channel added:\n'
                       f'**{channel.category.name}** - _{channel.name}_')

        data = {'room': True, 'parent': None}
        await self.config.channel(channel).set(data)
