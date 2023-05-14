import discord
import logging

from redbot.core import commands, Config

log = logging.getLogger('red.autoroles')


class Autoroles(commands.Cog):
    """Carl's Autoroles Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(enabled=False, roles=None)

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    async def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        log.debug('member: %s', member)
        config = await self.config.guild(member.guild).all()
        if config and config['enabled'] and config['roles']:
            roles = [member.guild.get_role(role) for role in config['roles']]
            await member.add_roles(*roles)

    @commands.group(name='autoroles', aliases=['ar'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def autoroles(self, ctx):
        """Options for managing Autoroles."""

    @autoroles.command(name='enable', aliases=['on'])
    async def autoroles_enable(self, ctx):
        """Enables Autoroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Autoroles is already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Autoroles has been enabled.')

    @autoroles.command(name='disable', aliases=['off'])
    async def autoroles_disable(self, ctx):
        """Disable Autoroles."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Autoroles is already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Autoroles has been disabled.')

    @autoroles.command(name='add')
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autoroles_add(self, ctx, *, role: discord.Role):
        """Add a role to autoroles."""
        roles = await self.config.guild(ctx.guild).roles() or []
        log.debug(roles)
        if role.id not in roles:
            if role >= ctx.guild.me.top_role:
                await ctx.send(f"Can not give out `@{role}` because it is "
                               f"higher than all the bot's current roles. ")
                return
            roles.append(role.id)
            await self.config.guild(ctx.guild).roles.set(roles)
            await ctx.send(f'Now giving members the role `@{role}`')
        else:
            await ctx.send(f'Already giving new members the role `@{role}`')

        if not await self.config.guild(ctx.guild).enabled():
            await ctx.send('**Warning:** Autoroles is **DISABLED**. Enable it.')

    @autoroles.command(name='remove', aliases=['del', 'delete'])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def autoroles_remove(self, ctx, role: discord.Role):
        """Removes a role from autoroles."""
        roles = await self.config.guild(ctx.guild).roles() or []
        log.debug(roles)
        if role.id in roles:
            roles.remove(role.id)
            await self.config.guild(ctx.guild).roles.set(roles)
            await ctx.send(f'Role `@{role.name}` removed from autoroles.')
        else:
            await ctx.send(f'Role `@{role.name}` is not an autorole.')

    @autoroles.command(name='status', aliases=['info', 'settings'])
    async def autoroles_status(self, ctx):
        """Get Autoroles status."""
        config = await self.config.guild(ctx.guild).all()
        status = '**Enabled**' if config['enabled'] else '**NOT ENABLED**'
        log.debug(config)
        if not config['roles']:
            await ctx.send(f'Status: {status}\nNo configured Autoroles...')
            return
        roles = [ctx.guild.get_role(role_id) for role_id in config['roles']]
        out = [f'Status: {status}\nAutoroles: ```']
        out = out + [f'\n@{role.name}' for role in roles]
        out.append('```')
        await ctx.send(''.join(out))
