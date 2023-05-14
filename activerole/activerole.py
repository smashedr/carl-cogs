import asyncio
import discord
import logging
import redis.asyncio as redis
from datetime import timedelta

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate

log = logging.getLogger('red.activerole')

ACTIVE_MINUTES = 10
LOOP_SLEEP_SECONDS = 60

REDIS_CONFIG = {
    'host': 'redis',
    'port': 6379,
    'db': 0,
    'password': None,
}

GLOBAL_SETTINGS = {
    'host': 'redis',
    'password': None,
    'enabled': False,
    'db': 0,
}

GUILD_SETTINGS = {
    'active_role': None,
    'roles': [],
    'channels': [],
}


class Activerole(commands.Cog):
    """Carl's Activerole Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(**GLOBAL_SETTINGS)
        self.config.register_guild(**GUILD_SETTINGS)
        self.loop = None
        self.redis = redis.Redis

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load Start')
        if await self.config.enabled():
            log.info(f'{self.__cog_name__}: Activerole Enabled')
            self.redis = redis.Redis(
                host=REDIS_CONFIG['host'],
                port=REDIS_CONFIG['port'],
                db=REDIS_CONFIG['db'],
                password=REDIS_CONFIG['password'],
            )
            self.loop = asyncio.create_task(self.cleanup_loop())
        log.info(f'{self.__cog_name__}: Cog Load Finish')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')
        if self.loop and not self.loop.cancelled():
            log.info('Stopping Loop')
            self.loop.cancel()

    async def cleanup_loop(self):
        # TODO: Determine why this is looping through ALL GUILDS!
        log.info('Starting Cleanup Loop in 10 seconds...')
        await asyncio.sleep(10)
        all_guilds = await self.config.all_guilds()
        while self is self.bot.get_cog('Activerole'):
            for guild_id, data in await AsyncIter(all_guilds.items()):
                guild = self.bot.get_guild(guild_id)
                role = guild.get_role(data['active_role'])
                log.debug(f'{guild} - {role}')
                for member in role.members:
                    key = f'{guild.id}-{member.id}'
                    log.debug(key)
                    if not await self.redis.exists(key):
                        log.debug('Inactive Remove Role: "%s"', member.name)
                        reason = f'Activerole user inactive.'
                        await member.remove_roles(role, reason=reason)
            await asyncio.sleep(LOOP_SLEEP_SECONDS)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_update(message)

    # @commands.Cog.listener()
    # async def on_message_edit(self, before, after: discord.Message):
    #     await self.process_update(after)

    async def process_update(self, message: discord.Message):
        member = message.author
        if member.bot:
            return
        if not await self.config.enabled():
            return
        if not await self.config.guild(member.guild).active_role():
            return

        role_id = await self.config.guild(member.guild).active_role()
        active_role = member.guild.get_role(role_id)
        if not active_role:
            log.warning('Role Not Found: %s', role_id)
            await self.config.guild(member.guild).active_role.set(None)
            log.warning('Disabled Activerole in guild: %s', member.guild.id)
            return

        exclude_channels = await self.config.guild(member.guild).channels()
        if message.channel.id in exclude_channels:
            return

        exclude_roles = await self.config.guild(member.guild).roles()
        needs_role = True
        for role in await AsyncIter(member.roles):
            if role.id in exclude_roles:
                return
            if active_role.id == role.id:
                needs_role = False

        key = f'{member.guild.id}-{member.id}'
        log.debug(key)
        expire = timedelta(minutes=ACTIVE_MINUTES)
        log.debug(expire)
        await self.redis.setex(key, expire, 1)
        if needs_role:
            log.debug('Applying Role "%s" to "%s"',
                      active_role.name, member.name)
            reason = f'Activerole user active.'
            await member.add_roles(active_role, reason=reason)

    @commands.group(name='activerole', aliases=['actr'])
    @commands.admin()
    async def activerole(self, ctx):
        """Options for configuring Activerole."""

    @activerole.command(name='role', aliases=['r'])
    async def activerole_role(self, ctx, *, role: discord.Role):
        """Set the role to apply to active members and enables Activerole."""
        await ctx.typing()
        log.debug(role)
        await self.config.guild(ctx.guild).active_role.set(role.id)
        await ctx.send(f'✅ Activerole set to role {role.mention}')

    @activerole.command(name='reset')
    async def activerole_reset(self, ctx, setting: str):
        """Reset all excluded roles for Activerole."""
        await ctx.typing()
        setting = setting.lower()
        log.debug(setting)
        if setting in ['channels', 'chann', 'chan', 'all']:
            await self.config.guild(ctx.guild).channels.set([])
        elif setting in ['roles', 'role', 'all']:
            await self.config.guild(ctx.guild).roles.set([])
        else:
            await ctx.send(f'Setting "{setting}" not found. Available: '
                           f'`channels` or `roles` or `all`')
            return
        await ctx.send(f'✅ Excludes have been painfully exterminated.')

    @activerole.command(name='disable', aliases=['d'])
    async def activerole_disable(self, ctx):
        """Disables Activerole, set a new role to re-enable it."""
        await ctx.typing()
        await self.config.guild(ctx.guild).active_role.set(None)
        await ctx.send(f'⛔ Activerole disabled in guild...')

    @activerole.command(name='status', aliases=['s', 'settings'])
    async def activerole_status(self, ctx):
        """Get Activerole status."""
        await ctx.typing()
        config = await self.config.guild(ctx.guild).all()
        status = 'Enabled' if await self.config.enabled() else 'DISABLED'
        out = [
            'Activerole Settings:',
            f'Global Status (bot owner): **{status}**',
            f'Active User Role: `{config["active_role"]}`',
            f'Excluded Channels: `{config["channels"]}`',
            f'Excluded Roles: `{config["roles"]}`',
        ]
        await ctx.send('\n'.join(out))

    @activerole.group(name='exclude', aliases=['e'])
    @commands.admin()
    async def acr_exclude(self, ctx):
        """Options for configuring Activerole."""

    @acr_exclude.command(name='role', aliases=['r', 'roles'])
    async def acr_exclude_role(self, ctx, *roles: discord.Role):
        """
        Exclude a role(s) from Activeroles. No spaces in role names.
        [p]activerole exclude role role1
        [p]activerole exclude roles role1 role2 another-role
        """
        await ctx.typing()
        log.debug(roles)
        if not roles:
            await ctx.send_help()
            return

        role_ids = [r.id for r in roles]
        log.debug(role_ids)
        async with self.config.guild(ctx.guild).roles() as exclude_roles:
            for role_id in role_ids:
                if role_id not in exclude_roles:
                    exclude_roles.append(role_id)
        exclude_roles = await self.config.guild(ctx.guild).roles()
        await ctx.send(f'Excluded Roles: ```{exclude_roles}```')

    @acr_exclude.command(name='channel', aliases=['c', 'channels'])
    async def acr_exclude_channel(self, ctx, *channels: discord.TextChannel):
        """
        Exclude a channel(s) from Activeroles.
        [p]activerole exclude channel channel1
        [p]activerole exclude channels channel1 channel2
        """
        await ctx.typing()
        log.debug(channels)
        if not channels:
            await ctx.send_help()
            return

        channel_ids = [r.id for r in channels]
        log.debug(channel_ids)
        async with self.config.guild(ctx.guild).channels() as exclude_channels:
            for channel_id in channel_ids:
                if channel_id not in exclude_channels:
                    exclude_channels.append(channel_id)
        exclude_channels = await self.config.guild(ctx.guild).channels()
        await ctx.send(f'Excluded Channels: ```{exclude_channels}```')

    @commands.group(name='activeroleconfig', aliases=['actrcfg'])
    @commands.is_owner()
    async def activeroleconfig(self, ctx):
        """Options for configuring Activerole."""

    @activeroleconfig.command(name='start', aliases=['on'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_start(self, ctx):
        """Starts Activerole loop."""
        await ctx.typing()
        if self.loop and not self.loop.cancelled():
            await ctx.send('Activerole loop already running.')
            return
        await self.config.enabled.set(True)
        self.loop = asyncio.create_task(self.cleanup_loop())
        await ctx.send('Activerole loop started.')

    @activeroleconfig.command(name='stop', aliases=['off'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_stop(self, ctx):
        """Stops Activerole loop."""
        await ctx.typing()
        await self.config.enabled.set(False)
        if not self.loop or self.loop.cancelled():
            await ctx.send('Activerole loop not running or stopped.')
            return
        self.loop.cancel()
        await ctx.send('Activerole loop stopped.')

    # @activeroleconfig.command(name='set', aliases=['s'])
    # @commands.max_concurrency(1, commands.BucketType.default)
    # async def activeroleconfig_set(self, ctx, setting):
    #     """Set optional Activerole settings."""
    #     await ctx.typing()
    #     if setting.lower() in ['password', 'pass']:
    #         await ctx.send('Check your DM.')
    #         channel = await ctx.author.create_dm()
    #         await channel.send('Please enter the password...')
    #         pred = MessagePredicate.same_context(channel=channel, user=ctx.author)
    #         try:
    #             response = await self.bot.wait_for("message", check=pred, timeout=30)
    #         except asyncio.TimeoutError:
    #             await channel.send(f'Request timed out. You need to start over.')
    #             return
    #         if response:
    #             password = response.content
    #             await channel.send('Password recorded successfully. You can delete '
    #                                'the message containing the password now!')
    #         else:
    #             log.debug('Error like wtf yo...')
    #             log.debug(pred.result)
    #             log.debug(response.content)
    #             return
    #         log.debug('SUCCESS password')
    #         log.debug(password)
    #         await self.config.password.set(password)
    #
    #     elif setting.lower() in ['hostname', 'host']:
    #         await ctx.channel.send('Please enter the hostname...')
    #         pred = MessagePredicate.same_context(ctx)
    #         try:
    #             response = await self.bot.wait_for("message", check=pred, timeout=30)
    #         except asyncio.TimeoutError:
    #             await ctx.channel.send(f'Request timed out. You need to start over.')
    #             return
    #         if response:
    #             host = response.content
    #             await ctx.channel.send('Hostname recorded successfully.')
    #         else:
    #             log.warning('response is None')
    #             log.info(response)
    #             log.info(pred.result)
    #             return
    #         log.debug('SUCCESS hostname')
    #         log.debug(host)
    #         await self.config.host.set(host)
    #     else:
    #         await ctx.send('Unknown setting. Try `hostname` or `password`.')
