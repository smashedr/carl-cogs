import aredis
import asyncio
import discord
import logging
import datetime
from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate

logger = logging.getLogger('red.activerole')

ACTIVE_MINUTES = 10
LOOP_SLEEP_SECONDS = 120


class Activerole(commands.Cog):
    """Carl's Activerole Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(host='redis', password=None, enabled=False)
        self.config.register_guild(active_role=None, roles=[], channels=[])
        self.host = None
        self.password = None
        self.loop = None
        self.client = None

    def cog_unload(self):
        if self.loop and not self.loop.cancelled():
            logger.debug('Unload Cog - Stopping Loop')
            self.loop.cancel()

    async def initialize(self):
        logger.info('Initializing Activerole Cog Start')
        self.host = await self.config.host()
        self.password = await self.config.password()
        self.client = aredis.StrictRedis(
            host=self.host, port=6379, db=3, password=self.password,
            retry_on_timeout=True,
        )
        if await self.config.enabled():
            self.loop = asyncio.create_task(self.cleanup_loop())
        logger.info('Initializing Activerole Cog Finished')

    async def cleanup_loop(self):
        logger.info('Starting Cleanup Loop in 10 seconds...')
        await asyncio.sleep(10)
        all_guilds = await self.config.all_guilds()
        while self is self.bot.get_cog('Activerole'):
            for guild_id, data in await AsyncIter(all_guilds.items()):
                guild = self.bot.get_guild(guild_id)
                role = guild.get_role(data['active_role'])
                # logger.debug(f'{guild} - {role}')
                for member in role.members:
                    key = f'{guild.id}-{member.id}'
                    # logger.debug(key)
                    if not await self.client.exists(key):
                        logger.debug('Inactive Remove Role: "%s"', member.name)
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
            logger.warning('Role Not Found: %s', role_id)
            await self.config.guild(member.guild).active_role.set(None)
            logger.warning('Disabled Activerole in guild: %s', member.guild.id)
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
        logger.debug(key)
        expire = datetime.timedelta(minutes=ACTIVE_MINUTES)
        logger.debug(expire)
        await self.client.setex(key, expire, True)
        if needs_role:
            logger.debug('Applying Role "%s" to "%s"',
                         active_role.name, member.name)
            reason = f'Activerole user active.'
            await member.add_roles(active_role, reason=reason)

    @commands.group(name='activerole', aliases=['acr'])
    @commands.admin()
    async def activerole(self, ctx):
        """Options for configuring Activerole."""

    @activerole.command(name='role', aliases=['r'])
    async def activerole_role(self, ctx, *, role: discord.Role):
        """Set the role to apply to active members and enables Activerole."""
        await ctx.trigger_typing()
        logger.debug(role)
        await self.config.guild(ctx.guild).active_role.set(role.id)
        await ctx.send(f'✅ Activerole set to role {role.mention}')

    @activerole.command(name='reset')
    async def activerole_reset(self, ctx, setting: str):
        """Reset all excluded roles for Activerole."""
        await ctx.trigger_typing()
        setting = setting.lower()
        logger.debug(setting)
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
        await ctx.trigger_typing()
        await self.config.guild(ctx.guild).active_role.set(None)
        await ctx.send(f'⛔ Activerole disabled in guild...')

    @activerole.command(name='status', aliases=['s', 'settings'])
    async def activerole_status(self, ctx):
        """Get Activerole status."""
        await ctx.trigger_typing()
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
        await ctx.trigger_typing()
        logger.debug(roles)
        if not roles:
            await ctx.send_help()
            return

        role_ids = [r.id for r in roles]
        logger.debug(role_ids)
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
        await ctx.trigger_typing()
        logger.debug(channels)
        if not channels:
            await ctx.send_help()
            return

        channel_ids = [r.id for r in channels]
        logger.debug(channel_ids)
        async with self.config.guild(ctx.guild).channels() as exclude_channels:
            for channel_id in channel_ids:
                if channel_id not in exclude_channels:
                    exclude_channels.append(channel_id)
        exclude_channels = await self.config.guild(ctx.guild).channels()
        await ctx.send(f'Excluded Channels: ```{exclude_channels}```')

    @commands.group(name='activeroleconfig', aliases=['arc'])
    @commands.is_owner()
    async def activeroleconfig(self, ctx):
        """Options for configuring Activerole."""

    @activeroleconfig.command(name='start', aliases=['on'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_start(self, ctx):
        """Starts Activerole loop."""
        await ctx.trigger_typing()
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
        await ctx.trigger_typing()
        await self.config.enabled.set(False)
        if not self.loop or self.loop.cancelled():
            await ctx.send('Activerole loop not running or stopped.')
            return
        self.loop.cancel()
        await ctx.send('Activerole loop stopped.')

    @activeroleconfig.command(name='set', aliases=['s'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_set(self, ctx, setting):
        """Set optional Activerole settings."""
        await ctx.trigger_typing()
        if setting.lower() in ['password', 'pass']:
            await ctx.send('Check your DM.')
            channel = await ctx.author.create_dm()
            await channel.send('Please enter the password...')
            pred = MessagePredicate.same_context(channel=channel, user=ctx.author)
            try:
                response = await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await channel.send(f'Request timed out. You need to start over.')
                return
            if response:
                password = response.content
                await channel.send('Password recorded successfully. You can delete '
                                   'the message containing the password now!')
            else:
                logger.debug('Error like wtf yo...')
                logger.debug(pred.result)
                logger.debug(response.content)
                return
            logger.debug('SUCCESS password')
            logger.debug(password)
            await self.config.password.set(password)

        elif setting.lower() in ['hostname', 'host']:
            await ctx.channel.send('Please enter the hostname...')
            pred = MessagePredicate.same_context(ctx)
            try:
                response = await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await ctx.channel.send(f'Request timed out. You need to start over.')
                return
            if response:
                host = response.content
                await ctx.channel.send('Hostname recorded successfully.')
            else:
                logger.warning('response is None')
                logger.info(response)
                logger.info(pred.result)
                return
            logger.debug('SUCCESS hostname')
            logger.debug(host)
            await self.config.host.set(host)
        else:
            await ctx.send('Unknown setting. Try `hostname` or `password`.')
