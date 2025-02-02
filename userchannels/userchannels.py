import asyncio
import discord
import logging
import random

from redbot.core import commands, Config
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.utils.predicates import ReactionPredicate

log = logging.getLogger('red.userchannels')


class Userchannels(commands.Cog):
    """Carl's Userchannels Cog"""

    room_names = {
        'a': ['Abode', 'Area', 'Airplane'],
        'b': ['Bistro', 'Bunk', 'Burrow'],
        'c': ['Camp', 'Castle', 'Cabin' 'Chamber', 'Crib'],
        'd': ['Dorm', 'Digs', 'Den'],
        'e': ['Encampment', 'Estate'],
        'f': ['Farm', 'Firehouse', 'Flat'],
        'g': ['Grotto', 'Grange'],
        'h': ['Hall', 'Harbor', 'Haven', 'Hotel', 'House', 'Hut'],
        'i': ['Inn', 'Igloo'],
        'j': ['Joint', 'Jet'],
        'k': ['Kiosk'],
        'l': ['Lodge'],
        'm': ['Manor', 'Meadow', 'Motel', 'Mansion'],
        'n': ['Nest'],
        'o': ['Oasis', 'Orchard'],
        'p': ['Pad', 'Paradise', 'Place', 'Pub'],
        'q': ['Quarters'],
        'r': ['Ranch', 'Range', 'Resort'],
        's': ['Square', 'Shack', 'Ship', 'Shelter', 'Startup'],
        't': ['Temple', 'Tent', 'Tower', 'Town', 'Turf'],
        'u': ['Union'],
        'v': ['Valley', 'Villa', 'Vineyard'],
        'w': ['Warehouse'],
        'xx': [''],
        'y': ['Yacht'],
        'zz': [''],
    }
    guild_default = {
        'enabled': False,
        'channel': None,
        'category': None,
    }
    channel_default = {
        'auto': False,
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_channel(**self.channel_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    async def process_remove(self, channel):
        if channel.members:
            return log.debug('Channel Not Empty')
        if not await self.config.channel(channel).auto():
            return log.debug('Channel Not Autochannel')

        try:
            channel_id = channel.id
            await channel.delete(reason='Userchannels channel empty.')
            log.debug('Removed Channel %s', channel_id)
        except discord.NotFound:
            log.debug('Channel Not Found')

        await self.config.channel(channel).clear()
        log.debug('Database Cleared')

    async def process_user_create(self, channel, member):
        config = await self.config.guild(member.guild).all()

        # get category
        dest_category = member.guild.get_channel(config['category'])

        # get channel name
        suffix = 'Room'
        if member.display_name[0].lower() in self.room_names:
            names = self.room_names[member.display_name[0].lower()]
            suffix = random.choice(names)
        channel_name = f"{member.display_name}'s {suffix}"
        log.debug(channel_name)

        # create channel
        voice_channel = await member.guild.create_voice_channel(
            name=channel_name,
            category=dest_category,
            reason='Userchannels autocreated channel.',
            user_limit=99,
            bitrate=member.guild.bitrate_limit,
        )
        await self.config.channel(voice_channel).auto.set(True)
        log.debug('Created Channel')

        # set permissions
        permissions = {
            'connect': True,
            'create_instant_invite': True,
            'deafen_members': True,
            'manage_channels': True,
            'manage_permissions': True,
            'move_members': True,
            'mute_members': True,
            'priority_speaker': True,
            'speak': True,
            'stream': True,
            'use_voice_activation': True,
            'view_channel': True,
        }
        await voice_channel.set_permissions(member, **permissions)

        # move member
        await member.move_to(voice_channel, reason='Userchannels moving user.')
        log.debug('Moved Member')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, part, join):
        if member.bot:
            return log.debug('bot')

        config = await self.config.guild(member.guild).all()
        if not config['enabled']:
            return log.debug('disabled')

        if join.channel:
            if config['channel'] == join.channel.id:
                log.debug('user channel join')
                await self.process_user_create(join.channel, member)

        if part.channel:
            if await self.config.channel(part.channel).auto():
                log.debug('auto channel part')
                await self.process_remove(part.channel)

    @commands.group(name='userchannels', aliases=['uc'])
    @commands.guild_only()
    @commands.admin()
    async def userchannels(self, ctx: commands.Context):
        """Options for managing Userchannels."""

    @userchannels.command(name='setup', aliases=['auto', 'a'])
    async def userchannels_setup(self, ctx: commands.Context):
        """AUTO Setup of Userchannels!"""
        msg = ('This will automatically create the Userchannels category, '
               'channel, and enable the module.\nProceed?')
        message = await ctx.send(msg, delete_after=30)
        pred = ReactionPredicate.yes_or_no(message, ctx.author)
        start_adding_reactions(message, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            await self.bot.wait_for('reaction_add', check=pred, timeout=30)
        except asyncio.TimeoutError:
            await ctx.send('Request timed out. Aborting.', delete_after=5)
            return await message.delete()

        if not pred.result:
            await ctx.send('Aborting.', delete_after=5)
            return await message.delete()

        await message.clear_reactions()
        await message.edit(content='Creating Userchannels now...')

        await asyncio.sleep(3.0)
        await message.delete()
        await ctx.send('✅ All Done.', delete_after=5)

        await self.config.guild(ctx.guild).enabled.set(True)
        category = await ctx.guild.create_category('USER ROOMS')
        log.debug('category: %s', category)
        log.debug('category.id: %s', category.id)
        await self.config.guild(ctx.guild).category.set(category.id)
        channel = await ctx.guild.create_voice_channel(
            name='👪 Get a Room',
            category=category,
            reason='Userchannels primary room.',
        )
        log.debug('channel: %s', channel)
        log.debug('channel.id: %s', channel.id)
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await self.userchannels_status(ctx)
        msg = ('User category and channel created and enabled!\n'
               'It should appear at the bottom of the list. You should '
               'drag the category towards the top so members can see it.')
        await ctx.send(msg)

    @userchannels.command(name='enable', aliases=['e', 'on'])
    async def userchannels_enable(self, ctx: commands.Context):
        """Enable Userchannels."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Userchannels is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Userchannels has been enabled.')

    @userchannels.command(name='disable', aliases=['d', 'off'])
    async def userchannels_disable(self, ctx: commands.Context):
        """Disable Userchannels."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Userchannels is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Userchannels has been disabled.')

    @userchannels.command(name='channel', aliases=['ch', 'chan', 'chann'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def userchannels_channel(self, ctx: commands.Context, *, channel: discord.VoiceChannel):
        """Set Userchannels channel."""
        log.debug(channel.id)
        await self.config.guild(ctx.guild).channel.set(channel.id)
        await ctx.send(f'Userchannels Userchannels Channel set to:\n**{channel.name}** - {channel.id}')

    @userchannels.command(name='category', aliases=['ca', 'cat'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def userchannels_category(self, ctx: commands.Context, *,
                                    category: discord.CategoryChannel):
        """Set Userchannels category."""
        log.debug(category.id)
        await self.config.guild(ctx.guild).category.set(category.id)
        await ctx.send(f'Userchannels Userchannels Category set to:\n**{category.name}** - {category.id}')

    @userchannels.command(name='status', aliases=['s', 'stat', 'settings'])
    async def userchannels_status(self, ctx: commands.Context):
        """Get Userchannels status."""
        config = await self.config.guild(ctx.guild).all()
        log.debug(config)
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        channel = ctx.guild.get_channel(config['channel'])
        category = ctx.guild.get_channel(config['category'])
        msg = ('Userchannels Userchannels Settings:\n'
               f'Global Enabled: {status}\n'
               f'Users Category: {category}'
               f'Users Channel: {channel}\n')
        await ctx.send(msg)
