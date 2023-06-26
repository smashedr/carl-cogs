import discord
import logging

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.autochannels')


class Autochannels(commands.Cog):
    """Carl's Autochannels Cog"""

    guild_default = {
        'enabled': False,
        'channel': None,
        'rooms': [],
    }
    channel_default = {
        'room': False,
        'auto': False,
        'parent': None,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_channel(**self.channel_default)

    async def cog_load(self):
        log.info('%s: Cog Load', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def process_create(self, channel, member):
        config = await self.config.channel(channel).all()
        log.debug(config)

        # get channel name
        if config['parent']:
            parent = member.guild.get_channel(config['parent'])
        else:
            parent = channel

        # get channels
        create, number = await self.check_create_number(
            channel.category.channels, parent.name)
        log.debug(create)
        log.debug(number)

        # create channel
        if create:
            new_channel = await parent.clone(
                name=f'{parent.name} {number}',
                reason='Autochannels autocreated channel.',
            )
            data = {'room': True, 'auto': True, 'parent': parent.id}
            await self.config.channel(new_channel).set(data)
            log.debug('Created Channel')

    @classmethod
    async def check_create_number(cls, channels, base_name):
        match_channels = []
        create = True
        number = 0
        async for channel in AsyncIter(channels, steps=10):
            if base_name.lower() in channel.name.lower():
                match_channels.append(channel)
                if not channel.members:
                    create = False
        if create:
            sorted_channels = sorted(match_channels, key=lambda d: d.name)
            name_list = [c.name for c in sorted_channels]
            number = cls.get_number(name_list)
        return create, number

    @staticmethod
    def get_number(name_list):
        for i, name in enumerate(name_list, start=1):
            if i == 1:
                continue
            try:
                num = int(name.split(' ')[-1])
            except Exception:
                i = i - 1
                continue
            if i == num:
                continue
            else:
                return i
        return len(name_list) + 1

    async def process_remove(self, channel, member):
        if channel.members:
            log.debug('Channel Not Empty')
            return
        if not await self.config.channel(channel).room():
            log.debug('Channel Not Autoroom')
            return

        config = await self.config.channel(channel).all()
        log.debug(config)
        if config['parent']:
            parent = member.guild.get_channel(config['parent'])
        else:
            parent = channel

        to_delete, match_channels = await self.check_channels_to_delete(
            parent.category.channels, parent.name)
        log.debug(to_delete)
        if not to_delete:
            log.debug('Nothing to Delete')
            return

        log.debug('Deleting the following:')
        channels = sorted(match_channels, key=lambda d: d.name, reverse=True)
        for i, channel in enumerate(channels):
            if i == to_delete:
                break

            log.debug(channel)
            if not await self.config.channel(channel).auto():
                log.debug('Not Auto Channel')
                continue
            if channel.members:
                log.debug('Channel Not Empty')
                return
            try:
                channel_id = channel.id
                await channel.delete(reason='Autochannels channel empty.')
                log.debug('Removed Channel %s', channel_id)
            except discord.NotFound:
                log.debug('Channel Not Found')

            await self.config.channel(channel).clear()
            log.debug('Database Cleared')

    @staticmethod
    async def check_channels_to_delete(channels, base_name):
        match_channels = []
        num_empty = 0
        async for channel in AsyncIter(channels, steps=10):
            if base_name.lower() in channel.name.lower():
                if not channel.members:
                    match_channels.append(channel)
                    num_empty = num_empty + 1

        to_delete = num_empty - 1 if num_empty >= 2 else 0
        log.debug(to_delete)
        return to_delete, match_channels

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, part, join):
        if member.bot:
            log.debug('bot')
            return

        config = await self.config.guild(member.guild).all()
        if not config['enabled']:
            log.debug('disabled')
            return

        if join.channel:
            if await self.config.channel(join.channel).room():
                log.debug('autoroom channel join')
                await self.process_create(join.channel, member)

        if part.channel:
            if await self.config.channel(part.channel).room():
                log.debug('autoroom channel part')
                await self.process_remove(part.channel, member)

    @commands.group(name='autochannels', aliases=['ac'])
    @commands.guild_only()
    @commands.admin()
    async def autochannels(self, ctx: commands.Context):
        """Options for managing Autochannels."""

    @autochannels.command(name='add', aliases=['a'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autochannels_add(self, ctx: commands.Context, *,
                               channel: discord.VoiceChannel):
        """
        Adds a channel to Autochannels Autorooms configuration.
        [p]autochannels add Channel Name
        """
        rooms = await self.config.guild(ctx.guild).rooms()
        log.debug(rooms)
        if channel.id in rooms:
            await ctx.send(f'Autochannels already configured:\n'
                           f'**{channel.category.name}** - _{channel.name}_')
            return

        await self.config.channel(channel).set({'room': True, 'parent': None})
        # rooms.append(channel.id)
        await self.config.guild(ctx.guild).rooms.set(rooms + [channel.id])
        await ctx.send(f'Autochannels Autorooms added:\n'
                       f'**{channel.category.name}** - _{channel.name}_')

    @autochannels.command(name='remove', aliases=['r', 'delete'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autochannels_remove(self, ctx: commands.Context, *,
                                  channel: discord.VoiceChannel):
        """
        Adds a channel to Autochannels Autorooms configuration.
        [p]autochannels add Channel Name
        """
        rooms = await self.config.guild(ctx.guild).rooms()
        log.debug(rooms)
        if channel.id not in rooms:
            await ctx.send(f'Channel **{channel.name}** not in config.')
            return

        rooms.remove(channel.id)
        await self.config.channel(channel).clear()
        await self.config.guild(ctx.guild).rooms.set(rooms)
        await ctx.send(f'Channel **{channel.name}** removed from config.')

    @autochannels.command(name='enable', aliases=['e', 'on'])
    async def autochannels_enable(self, ctx: commands.Context):
        """Enable Autochannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Autochannels is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Autochannels has been enabled.')

    @autochannels.command(name='disable', aliases=['d', 'off'])
    async def autochannels_disable(self, ctx: commands.Context):
        """Disable Autochannels Globally."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Autochannels is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Autochannels has been disabled.')

    @autochannels.command(name='status', aliases=['s', 'stat', 'settings'])
    async def autochannels_status(self, ctx: commands.Context):
        """Get Autochannels status."""
        config = await self.config.guild(ctx.guild).all()
        log.debug(config)
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        out = f'Autochannels Settings:\n' \
              f'Global Enabled: {status}\n' \
              f'Autochannels: {config["rooms"]}'
        await ctx.send(out)
