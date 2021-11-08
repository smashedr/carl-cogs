import discord
import logging
from redbot.core import commands, Config

logger = logging.getLogger('red.autorole')


class Autorole(commands.Cog):
    """Carl's Autorole Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(enabled=False, roles=None)

    async def initialize(self) -> None:
        logger.info('Initializing Autorole Cog')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        logger.debug('member: %s', member)
        config = await self.config.guild(member.guild).all()
        if config['enabled'] and config['roles']:
            roles = [member.guild.get_role(role) for role in config['roles']]
            await member.add_roles(*roles)

    @commands.group(name='autorole')
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def autorole(self, ctx):
        """Options for sending welcome messages."""

    @autorole.command(name='enable', aliases=['on'])
    async def autorole_enable(self, ctx):
        """Enables Autorole."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Autorole is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Autorole has been enabled.')

    @autorole.command(name='disable', aliases=['off'])
    async def autorole_disable(self, ctx):
        """Disable Autorole."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Autorole is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Autorole has been disabled.')

    @autorole.command(name='add')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autorole_add(self, ctx, role: discord.Role):
        """Add a role to autorole."""
        roles = await self.config.guild(ctx.guild).roles() or []
        logger.debug(roles)
        if role.id not in roles:
            if role >= ctx.guild.me.top_role:
                await ctx.send(f"Can not give out `@{role}` because it is "
                               f"higher than all the bot's current roles. ")
            else:
                roles.append(role.id)
                await self.config.guild(ctx.guild).roles.set(roles)
                await ctx.send(f'Now giving members the role `@{role}`')
        else:
            await ctx.send(f'Already giving new members the role `@{role}`')

    @autorole.command(name='remove', aliases=['del', 'delete'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autorole_remove(self, ctx, role: discord.Role):
        """Removes a role from autorole."""
        roles = await self.config.guild(ctx.guild).roles() or []
        logger.debug(roles)
        if role.id in roles:
            roles.remove(role.id)
            await self.config.guild(ctx.guild).roles.set(roles)
            await ctx.send(f'Role `@{role.name}` removed from autoroles.')
        else:
            await ctx.send(f'Role `@{role.name}` is not an autorole.')

    @autorole.command(name='status', aliases=['info', 'settings'])
    async def autorole_status(self, ctx):
        """Get Autorole status."""
        config = await self.config.guild(ctx.guild).all()
        logger.debug(config)
        roles = [ctx.guild.get_role(role_id) for role_id in config['roles']]
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        out = [f'Status: {status}\nAutoroles: ```']
        out = out + [f'\n@{role.name}' for role in roles]
        out.append('```')
        await ctx.send(''.join(out))
