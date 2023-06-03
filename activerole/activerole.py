import discord
import logging
import redis.asyncio as redis
from datetime import timedelta
from typing import Optional

from discord.ext import tasks
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter

log = logging.getLogger('red.activerole')


class ActiveRole(commands.Cog):
    """Carl's ActiveRole Cog"""

    guild_default = {
        'active_role': None,
        'active_minutes': 10,
        'roles': [],
        'channels': [],
    }

    def __init__(self, bot):
        self.bot: Red = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.redis: Optional[redis.Redis] = None

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.redis.ping()
        self.main_loop.start()
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.main_loop.cancel()

    @tasks.loop(minutes=2.0)
    async def main_loop(self):
        await self.bot.wait_until_ready()
        # log.debug('%s: Run Loop: main_loop', self.__cog_name__)
        all_guilds = await self.config.all_guilds()
        for guild_id, data in await AsyncIter(all_guilds.items()):
            guild = self.bot.get_guild(guild_id)
            role = guild.get_role(data['active_role'])
            # log.debug('role.id: %s', role.id)
            for member in role.members:
                key = f'active:{guild.id}-{member.id}'
                # log.debug('key: %s', key)
                if not await self.redis.exists(key):
                    log.debug('Inactive Remove Role: "%s"', member.name)
                    reason = f'Activerole user inactive.'
                    await member.remove_roles(role, reason=reason)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_update(message)

    # @commands.Cog.listener()
    # async def on_message_edit(self, before, after: discord.Message):
    #     await self.process_update(after)

    async def process_update(self, message: discord.Message):
        member: discord.Member = message.author
        guild: discord.Guild = message.guild
        if member.bot:
            return
        config: dict = await self.config.guild(guild).all()
        # log.debug('config: %s', config)
        if not config['active_role']:
            return
        active_role: discord.Role = member.guild.get_role(config['active_role'])
        if not active_role:
            log.warning('Role Not Found: %s', config['active_role'])
            await self.config.guild(member.guild).active_role.set(None)
            log.warning('Disabled Activerole in guild: %s', member.guild.id)
            return
        if message.channel.id in config['channels']:
            return

        needs_role = True
        for role in await AsyncIter(member.roles):
            if role.id in config['roles']:
                return
            if active_role.id == role.id:
                needs_role = False

        key = f'active:{member.guild.id}-{member.id}'
        expire = timedelta(minutes=config['active_minutes'])
        await self.redis.setex(key, expire, 1)
        if needs_role:
            log.debug('Applying Role "%s" to "%s"',
                      active_role.name, member.name)
            reason = f'Activerole user active.'
            await member.add_roles(active_role, reason=reason)

    @commands.group(name='activerole', aliases=['acr'])
    @commands.admin()
    async def activerole(self, ctx: commands.Context):
        """Options for configuring Activerole."""

    @activerole.command(name='role', aliases=['r'])
    async def activerole_role(self, ctx: commands.Context, *,
                              role: discord.Role):
        """Set the role to apply to active members and enables Activerole."""
        await ctx.typing()
        log.debug(role)
        await self.config.guild(ctx.guild).active_role.set(role.id)
        await ctx.send(f'✅ Activerole set to role {role.mention}')

    @activerole.command(name='reset')
    async def activerole_reset(self, ctx: commands.Context, setting: str):
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
    async def activerole_disable(self, ctx: commands.Context):
        """Disables Activerole, set a new role to re-enable it."""
        await ctx.typing()
        await self.config.guild(ctx.guild).active_role.set(None)
        await ctx.send(f'⛔ Activerole disabled in guild...')

    @activerole.command(name='status', aliases=['s', 'settings'])
    async def activerole_status(self, ctx: commands.Context):
        """Get Activerole status."""
        await ctx.typing()
        config = await self.config.guild(ctx.guild).all()
        # status = 'Enabled' if await self.config.enabled() else 'DISABLED'
        out = [
            'Activerole Settings:',
            # f'Global Status (bot owner): **{status}**',
            f'Active User Role: `{config["active_role"]}`',
            f'Excluded Channels: `{config["channels"]}`',
            f'Excluded Roles: `{config["roles"]}`',
            f'Active Minutes: `{config["active_minutes"]}`',
        ]
        await ctx.send('\n'.join(out))

    @activerole.group(name='exclude', aliases=['e'])
    @commands.admin()
    async def acr_exclude(self, ctx):
        """Options for configuring Activerole."""

    @acr_exclude.command(name='role', aliases=['r', 'roles'])
    async def acr_exclude_role(self, ctx: commands.Context, *roles: discord.Role):
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
    async def acr_exclude_channel(self, ctx: commands.Context,
                                  *channels: discord.TextChannel):
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
