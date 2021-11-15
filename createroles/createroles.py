import discord
import logging

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter

logger = logging.getLogger('red.createroles')

WOW_CLASSES = {
    'Druid': '16743434',
    'Hunter': '11195250',
    'Mage': '4179947',
    'Paladin': '16026810',
    'Priest': '16777215',
    'Rogue': '16774248',
    'Shaman': '28893',
    'Warlock': '8882414',
    'Warrior': '13015917',
}

ROLE_SETS = {
    'wowclasses': WOW_CLASSES,
}


class Createroles(commands.Cog):
    """Carl's Createroles Cog"""
    def __init__(self, bot):
        self.bot = bot
        # self.config = Config.get_conf(self, 1337, True)
        # self.config.register_guild(rr=None, at=None)

    async def initialize(self) -> None:
        logger.debug('Initializing Createroles Cog')

    async def create_role_set(self, ctx, role_set):
        logger.debug(role_set)

        logger.debug(ctx.guild.roles)
        logger.debug(ctx.author.name)

        results = []
        async for name, color in AsyncIter(role_set.items()):
            logger.debug(f'{name} - {color}')
            roles = [r for r in ctx.guild.roles if r.name == name]
            role = roles[0] if roles else None
            if role:
                results.append(f'`@{role.name}` - Already Exist')
                logger.debug('Role %s already exists.', name)
                continue
            logger.debug('Creating Role: %s', name)
            role = await ctx.guild.create_role(
                name=name, color=int(color),
                reason=f'Carl createroles command used by {ctx.author.name}',
            )
            results.append(f'`@{role.name}` - Created Role')

        return results

    @commands.group(name='createroles', aliases=['cr'])
    @commands.guild_only()
    @commands.admin()
    async def createroles(self, ctx):
        """Manage React Roles and the messages their attached too."""

    @createroles.command(name='list', aliases=["l"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_list(self, ctx):
        """List configured role sets that can be created."""
        role_sets = list(ROLE_SETS.keys())
        await ctx.send(f'Available role sets:\n{role_sets}')

    @createroles.command(name='create', aliases=["c"])
    @commands.max_concurrency(1, commands.BucketType.guild)
    async def createroles_create(self, ctx, *, name: str):
        """Create a Role set with the given name. View role sets with `list`."""
        name = name.lower()
        logger.debug(name)
        if name in ROLE_SETS:
            await ctx.send(f'Creating role set: {name}')
            results = await self.create_role_set(ctx, ROLE_SETS[name])
            out = [f'Role Creation Complete. Results:\n']
            for result in results:
                out.append(result + '\n')
            await ctx.send(''.join(out).rstrip())
        else:
            await ctx.send(f'Role set not found: {name}\n'
                           f'Use [p]createroles list')
