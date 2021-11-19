import aredis
import asyncio
import discord
import logging
import datetime
from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils.predicates import MessagePredicate

logger = logging.getLogger('red.activerole')


class Activerole(commands.Cog):
    """Carl's Activerole Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_global(host='redis', password=None, enabled=False)
        self.config.register_guild(role=None, excludes=[])
        self.host = None
        self.password = None
        self.loop = None
        self.client = None

    def cog_unload(self):
        if self.loop:
            self.loop.cancel()

    async def initialize(self):
        logger.debug("Initializing Activerole Cog Start")
        self.host = await self.config.host()
        self.password = await self.config.password()
        logger.debug(self.host)
        logger.debug(self.password)
        self.client = aredis.StrictRedis(
            host=self.host, port=6379, db=3, password=self.password
        )
        if await self.config.enabled():
            self.loop = asyncio.create_task(self.cleanup_loop())
        logger.debug("Initializing Activerole Cog Finished")

    async def cleanup_loop(self):
        logger.debug('Executing Loop')
        all_guilds = await self.config.all_guilds()
        while self is self.bot.get_cog('Activerole'):
            logger.debug('Starting Loop')
            for guild_id, data in await AsyncIter(all_guilds.items()):
                # logger.debug(guild_id)
                # logger.debug(data)
                guild = self.bot.get_guild(guild_id)
                role = guild.get_role(data['role'])
                for member in role.members:
                    if not await self.client.exists(member.id):
                        logger.debug('Inactive Member: "%s"', member.name)
                        reason = f'Activerole user inactive.'
                        await member.remove_roles(role, reason=reason)

            logger.debug('Finished Loop - Sleeping 30')
            await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_update(message.author)

    @commands.Cog.listener()
    async def on_message_edit(self, before, message: discord.Message):
        await self.process_update(message.author)

    async def process_update(self, member: discord.Member):
        logger.debug(member)
        if member.bot:
            return
        if not await self.config.enabled():
            return
        if not await self.config.guild(member.guild).role():
            return

        role_id = await self.config.guild(member.guild).role()
        active_role = member.guild.get_role(role_id)
        if not active_role:
            # maybe disable it here?
            logger.warning('Role Not Found: %s', role_id)
            return

        excludes = await self.config.guild(member.guild).excludes()
        needs_role = True
        for role in await AsyncIter(member.roles):
            if role.id in excludes:
                logger.debug('Member "%s" has excluded role "%s".',
                             member.name, role.name)
                return
            if active_role.id == role.id:
                needs_role = False

        logger.debug('Active Member: "%s"', member.name)
        if needs_role:
            logger.debug('Applying Role: "%s"', active_role.name)
            reason = f'Activerole user active.'
            await member.add_roles(active_role, reason=reason)
        await self.client.setex(member.id, datetime.timedelta(minutes=2), True)

    @commands.group(name='activerole', aliases=['acr'])
    @commands.admin()
    async def activerole(self, ctx):
        """Options for configuring Activerole."""

    @activerole.command(name='role', aliases=['r'])
    async def activerole_role(self, ctx, *, role: discord.Role):
        """Set the role to apply to active members and enables Activerole."""
        logger.debug(role)
        await self.config.guild(ctx.guild).role.set(role.id)
        await ctx.send(f'✅ Activerole set to role {role.mention}')

    @activerole.command(name='exclude', aliases=['e'])
    async def activerole_exclude(self, ctx, *roles: discord.Role):
        """
        List of Discord Roles to exclude from Activerole. No spaces in names.
        [p]activerole exclude role1
        [p]activerole exclude role1 role2 another-role
        """
        logger.debug(roles)
        if not roles:
            await ctx.send_help()
            return

        role_ids = [r.id for r in roles]
        logger.debug(role_ids)
        async with self.config.guild(ctx.guild).excludes() as excludes:
            for role_id in role_ids:
                if role_id not in excludes:
                    excludes.append(role_id)
        excludes = await self.config.guild(ctx.guild).excludes()
        await ctx.send(f'✅ Excluded Roles: ```{excludes}```')

    @activerole.command(name='reset')
    async def activerole_reset(self, ctx):
        """Reset all excluded roles for Activerole."""
        await self.config.guild(ctx.guild).excludes.set([])
        await ctx.send(f'✅ Excludes have been painfully exterminated.')

    @activerole.command(name='disable', aliases=['d'])
    async def activerole_disable(self, ctx, *, role: discord.Role):
        """Disables Activerole, set a new role to re-enable it."""
        logger.debug(role)
        await self.config.guild(ctx.guild).role.set(None)
        await ctx.send(f'⛔ Activerole disabled in guild...')

    @commands.group(name='activeroleconfig', aliases=['arc'])
    @commands.is_owner()
    async def activeroleconfig(self, ctx):
        """Options for configuring Activerole."""

    @activeroleconfig.command(name='start', aliases=['on'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_start(self, ctx):
        """Starts Activerole loop."""
        if self.loop:
            await ctx.send('Activerole loop already running.')
            return
        self.loop = asyncio.create_task(self.cleanup_loop())
        await self.config.enabled.set(True)
        await ctx.send('Activerole loop started.')

    @activeroleconfig.command(name='stop', aliases=['off'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_stop(self, ctx):
        """Stops Activerole loop."""
        await self.config.enabled.set(False)
        if not self.loop:
            await ctx.send('Activerole loop not running.')
            return
        self.loop.cancel()
        await ctx.send('Activerole loop stopped.')

    @activeroleconfig.command(name='set', aliases=['s'])
    @commands.max_concurrency(1, commands.BucketType.default)
    async def activeroleconfig_set(self, ctx, setting):
        """Set optional Activerole settings."""
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
                logger.debug('Error like wtf yo...')
                logger.debug(pred.result)
                logger.debug(response.content)
                return
            logger.debug('SUCCESS hostname')
            logger.debug(host)
            await self.config.host.set(host)
